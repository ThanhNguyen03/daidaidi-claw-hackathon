"""
Agent Knowledge & Skill Ingest Tool
=====================================
Indexes all agent skills/ and knowledge/ markdown files into LanceDB
so agents can retrieve only what's relevant per request (RAG), instead
of re-reading every file on every call.

Design
------
- Runs ONCE at app startup via `ingest_all_agents()`.
- Idempotent: each source file is tracked by a content hash stored in
  `data/ingest_state.json`. Files that haven't changed are skipped.
- Chunking: each markdown file is split at H2/H3 headings so retrievals
  return coherent sections, not arbitrary byte windows.
- Metadata stored with every chunk:
    agent   (str)  - agent name, e.g. "compliance"
    type    (str)  - "skill" | "knowledge"
    source  (str)  - unique key  "compliance/knowledge/vn-data-privacy.md"
    file    (str)  - filename without extension

Can also be run standalone:
    python -m tools.ingest [--force] [--agent <name>]
"""

import os
import re
import sys
import json
import hashlib
import asyncio
import argparse
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

AGENTS_DIR = Path(__file__).parent.parent / "agents"
STATE_FILE = Path(__file__).parent.parent / "data" / "ingest_state.json"
CHUNK_MIN_CHARS = 200   # skip tiny headings that have no body
CHUNK_MAX_CHARS = 2000  # split oversized sections to stay token-friendly


# ---------------------------------------------------------------------------
# Chunker
# ---------------------------------------------------------------------------

def _chunk_markdown(text: str, source: str) -> list[dict]:
    """
    Split a markdown file at H2/H3 headings.
    Each chunk includes the heading as the first line.
    Returns list of {text, section} dicts.
    """
    # Split on lines that start with ## or ###
    pattern = re.compile(r'^(#{2,3} .+)$', re.MULTILINE)
    parts = pattern.split(text)

    chunks = []

    # parts[0] is the text before the first heading (preamble / frontmatter)
    preamble = parts[0].strip()
    if len(preamble) >= CHUNK_MIN_CHARS:
        chunks.append({"text": preamble, "section": "preamble"})

    i = 1
    while i < len(parts) - 1:
        heading = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        combined = f"{heading}\n\n{body}" if body else heading

        # Split oversized chunks
        if len(combined) > CHUNK_MAX_CHARS:
            # Keep first CHUNK_MAX_CHARS, discard rest (heading context preserved)
            combined = combined[:CHUNK_MAX_CHARS]

        if len(combined) >= CHUNK_MIN_CHARS:
            chunks.append({"text": combined, "section": heading})

        i += 2

    # If no headings found at all, treat the whole file as one chunk
    if not chunks and len(text.strip()) >= CHUNK_MIN_CHARS:
        chunks.append({"text": text.strip(), "section": "full"})

    return chunks


# ---------------------------------------------------------------------------
# State (hash-based staleness detection)
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    """Load ingest state from disk (file hash → indexed flag)."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _file_hash(path: Path) -> str:
    """MD5 hash of file content (fast staleness check)."""
    return hashlib.md5(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Core ingest logic
# ---------------------------------------------------------------------------

async def ingest_agent(agent_name: str, force: bool = False) -> dict[str, int]:
    """
    Index all skills/ and knowledge/ files for one agent.

    Hash-check priority:
      1. AgentBase Memory (if AGENTBASE_MEMORY_ID is set) — persists hash records across
         restarts.  LanceDB is always rebuilt via re-embedding through the configured
         embedding provider (volatile in containers).
      2. Local ingest_state.json — file-based fallback; skips re-embed only when LanceDB
         data also persists (local dev with a persistent ./data directory).

    Returns {"indexed": N, "skipped": N, "errors": N}
    """
    from repos.kb_repo import get_kb_repo, HybridKBRepo

    kb = get_kb_repo()
    local_state = _load_state()
    stats = {"indexed": 0, "skipped": 0, "errors": 0}

    for doc_type in ("skills", "knowledge"):
        dir_path = AGENTS_DIR / agent_name / doc_type
        if not dir_path.exists():
            continue

        for md_file in sorted(dir_path.glob("*.md")):
            source_key = f"{agent_name}/{doc_type}/{md_file.name}"
            file_hash = _file_hash(md_file)

            skip_memory_update = False
            if not force:
                if isinstance(kb, HybridKBRepo) and kb.using_agentbase:
                    cached_hash = await kb.get_cached_hash(source_key)
                    if cached_hash == file_hash:
                        if local_state.get(source_key) == file_hash:
                            # Both Memory and local hash match: LanceDB was populated
                            # in this process environment and is still current.
                            stats["skipped"] += 1
                            continue
                        skip_memory_update = True  # Memory hash current; just re-embed
                else:
                    # Local dev without AgentBase: LanceDB persists on disk.
                    if local_state.get(source_key) == file_hash:
                        stats["skipped"] += 1
                        continue

            try:
                text = md_file.read_text(encoding="utf-8")
                chunks = _chunk_markdown(text, source_key)

                if not chunks:
                    print(f"  [ingest] {source_key}: no chunks extracted, skipping")
                    stats["skipped"] += 1
                    continue

                # Remove old version of this file from the index
                await kb.delete_by_source(source_key)

                # Build documents list
                docs = []
                for chunk in chunks:
                    docs.append((
                        chunk["text"],
                        {
                            "agent": agent_name,
                            "type": doc_type.rstrip("s"),   # "skill" | "knowledge"
                            "source": source_key,
                            "file": md_file.stem,
                            "section": chunk["section"],
                        },
                    ))

                # add_documents() embeds + writes to LanceDB.
                # update_memory=False when hash already matches in AgentBase Memory
                # (no need to re-write the same hash record).
                if isinstance(kb, HybridKBRepo):
                    await kb.add_documents(
                        docs,
                        source_key=source_key,
                        file_hash=file_hash,
                        update_memory=not skip_memory_update,
                    )
                else:
                    await kb.add_documents(docs)

                local_state[source_key] = file_hash
                label = "re-embedded (hash unchanged)" if skip_memory_update else "indexed"
                print(f"  [ingest] {source_key}: {len(docs)} chunk(s) {label}")
                stats["indexed"] += len(docs)

            except Exception as e:
                print(f"  [ingest] ERROR {source_key}: {e}")
                stats["errors"] += 1

    _save_state(local_state)
    return stats


async def ingest_all_agents(force: bool = False) -> None:
    """
    Walk every agent directory and index all skills/knowledge.
    Called once at app startup.

    Optimized: if all files are unchanged (force=False), skip KB initialization entirely.
    """
    if not AGENTS_DIR.exists():
        print("[ingest] agents dir not found, skipping")
        return

    # PRE-CHECK: Scan all files to see if any actually changed.
    # This avoids initializing LanceDB (and loading the embedding provider) if nothing is new.
    local_state = _load_state()
    any_changed = False
    if not force:
        for agent_dir in sorted(AGENTS_DIR.iterdir()):
            if not agent_dir.is_dir() or agent_dir.name.startswith("_") or agent_dir.name.startswith("."):
                continue
            for doc_type in ("skills", "knowledge"):
                dir_path = agent_dir / doc_type
                if not dir_path.exists():
                    continue
                for md_file in dir_path.glob("*.md"):
                    source_key = f"{agent_dir.name}/{doc_type}/{md_file.name}"
                    file_hash = _file_hash(md_file)
                    if local_state.get(source_key) != file_hash:
                        any_changed = True
                        break
                if any_changed:
                    break
            if any_changed:
                break
    else:
        any_changed = True  # force=True means always re-index

    # If nothing changed and AgentBase Memory has up-to-date hashes, skip entirely
    if not any_changed:
        print("[ingest] skipped — all files unchanged")
        return

    agent_dirs = [
        d for d in sorted(AGENTS_DIR.iterdir())
        if d.is_dir() and not d.name.startswith("_") and not d.name.startswith(".")
    ]

    total = {"indexed": 0, "skipped": 0, "errors": 0}
    for agent_dir in agent_dirs:
        agent_name = agent_dir.name
        # Only process dirs that have at least one skill/knowledge folder
        has_content = any(
            (agent_dir / dt).exists()
            for dt in ("skills", "knowledge")
        )
        if not has_content:
            continue

        print(f"[ingest] agent: {agent_name}")
        stats = await ingest_agent(agent_name, force=force)
        for k, v in stats.items():
            total[k] += v

    print(
        f"[ingest] done — indexed: {total['indexed']} chunks, "
        f"skipped: {total['skipped']} unchanged, "
        f"errors: {total['errors']}"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Ingest agent skills/knowledge into LanceDB")
    parser.add_argument("--force", action="store_true", help="Re-index even unchanged files")
    parser.add_argument("--agent", default=None, help="Ingest only this agent (default: all)")
    args = parser.parse_args()

    # Add backend/ to path so imports work
    sys.path.insert(0, str(Path(__file__).parent.parent))

    if args.agent:
        asyncio.run(ingest_agent(args.agent, force=args.force))
    else:
        asyncio.run(ingest_all_agents(force=args.force))


if __name__ == "__main__":
    main()
