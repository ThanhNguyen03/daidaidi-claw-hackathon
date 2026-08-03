"""
Knowledge Loader
================
The single place in the system that reads agent knowledge (BRD §5.1).

Skills never open a reference file or query a store themselves — they ask this
module. That is what makes the §14 log meaningful: if a document reached a
prompt, it went through here.

Why a lookup table instead of a vector search
---------------------------------------------
Each agent's SKILL.md declares the reference files it owns, with a real
description of what each one is for. A cheap selector call picks the ones this
task needs and the whole file is injected — not similarity-matched fragments.

At ~250KB of corpus this is both more accurate and far easier to debug than
embedding search: you can read the log and see exactly which documents the
model was given (BRD §5, "Về việc có cần vector DB không"). It also removes the
runtime dependency on an embedding endpoint, which previously failed closed and
silently — a 401 during startup ingest left the knowledge base empty with
nothing but a warning on stdout.

Contract
--------
- Content is cached in memory, invalidated by mtime (§5.5)
- Within one request a document is read once; a second agent asking for the
  same content is served from the ledger (§5.2), matched by content hash so the
  same text under two paths still counts as one document (§5.3)
- Injected knowledge is capped per model call; the lowest-priority documents are
  dropped and what was dropped is logged (§5.4)
- A read failure raises. The caller must surface "no knowledge for this" rather
  than let the model answer from general knowledge (§5.6)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS_DIR = os.path.abspath(os.path.join(_HERE, "..", "agents"))

# Budget for the knowledge block of a single model call. Roughly 12k tokens of
# mixed Vietnamese/English — large enough for two or three full reference files,
# small enough that the system prompt does not crowd out the conversation.
KNOWLEDGE_CHAR_BUDGET = int(os.getenv("KNOWLEDGE_CHAR_BUDGET", "48000"))

# Catalogs this size or smaller skip the selector call and load everything.
SELECTOR_MIN_CATALOG = int(os.getenv("KNOWLEDGE_SELECTOR_MIN_CATALOG", "2"))

# Logical skill name -> directory under backend/agents. Mirrors
# tools/ingest.py:AGENT_SOURCE_PRIORITY so both paths agree on where an agent lives.
AGENT_DIRS: dict[str, list[str]] = {
    "sales_orchestrator": ["sales_orchestrator_agent"],
    "requirement_elicitation": ["requirement_elicitation_agent"],
    "central_agent": ["sales_orchestrator_agent"],
    "market_strategy": ["market_strategy_agent"],
    "product_solution": ["product_solution_agent"],
    "compliance": ["compliance_policy_agent"],
    "client_simulator": ["client_simulator_agent"],
    "proposal_assembler": ["proposal_assembler_agent"],
    "wireframe_designer": ["wireframe_designer_agent"],
    "figma_wireframe": ["figma_wireframe_agent"],
    "design": ["design"],
    "cs_agent": ["cs-agent"],
    "predict_agent": ["predict-agent"],
}


class KnowledgeUnavailable(RuntimeError):
    """Raised when a declared reference cannot be read. Never swallow this —
    §5.6 requires the step to stop rather than let the model improvise."""


@dataclass(frozen=True)
class ReferenceEntry:
    filename: str
    purpose: str


@dataclass
class LoadedDoc:
    filename: str
    content: str
    sha: str


@dataclass
class RequestLedger:
    """Per-request record of what knowledge was served, for dedup and logging."""

    request_id: str
    _by_sha: dict[str, str] = field(default_factory=dict)      # sha -> first filename
    _requests: dict[str, int] = field(default_factory=dict)    # sha -> times asked
    dropped: list[tuple[str, str]] = field(default_factory=list)  # (agent, filename)

    def note(self, sha: str, filename: str) -> bool:
        """Record a request for a document. Returns True the first time it is seen."""
        self._requests[sha] = self._requests.get(sha, 0) + 1
        if sha in self._by_sha:
            return False
        self._by_sha[sha] = filename
        return True

    def summary(self) -> str:
        reused = [f"{name}×{self._requests[sha]}" for sha, name in self._by_sha.items()
                  if self._requests[sha] > 1]
        parts = [f"{len(self._by_sha)} unique doc(s)"]
        if reused:
            parts.append("reused: " + ", ".join(reused))
        if self.dropped:
            parts.append("dropped: " + ", ".join(f"{a}/{f}" for a, f in self.dropped))
        return " | ".join(parts)


# --------------------------------------------------------------------------
# Catalog: what a given agent declares it can load
# --------------------------------------------------------------------------

# Matches the rows of the "Reference Skills List" table:
#   | [file.md](reference/file.md) | Purpose text |
_ROW_RE = re.compile(
    r"^\|\s*\[(?P<name>[^\]]+\.md)\]\([^)]*\)\s*\|\s*(?P<purpose>.+?)\s*\|\s*$",
    re.MULTILINE,
)


def parse_catalog(skill_md: str) -> list[ReferenceEntry]:
    """Extract the declared reference files from a SKILL.md.

    Returns [] when the skill declares no table — callers must treat that as
    "this agent has no retrievable knowledge", not as an error.
    """
    entries: list[ReferenceEntry] = []
    seen: set[str] = set()
    for m in _ROW_RE.finditer(skill_md):
        name = m.group("name").strip()
        if name in seen:
            continue
        seen.add(name)
        entries.append(ReferenceEntry(filename=name, purpose=m.group("purpose").strip()))
    return entries


def agent_reference_dir(agent: str) -> Optional[str]:
    for candidate in AGENT_DIRS.get(agent, [agent, f"{agent}_agent"]):
        path = os.path.join(AGENTS_DIR, candidate, "reference")
        if os.path.isdir(path):
            return path
    return None


# --------------------------------------------------------------------------
# Reading, with an mtime-keyed cache
# --------------------------------------------------------------------------

_FILE_CACHE: dict[str, tuple[float, str, str]] = {}  # path -> (mtime, content, sha)


def _read_cached(path: str) -> tuple[str, str]:
    """Return (content, sha256). Raises KnowledgeUnavailable on any read problem."""
    try:
        mtime = os.path.getmtime(path)
    except OSError as exc:
        raise KnowledgeUnavailable(f"cannot stat {path}: {exc}") from exc

    hit = _FILE_CACHE.get(path)
    if hit and hit[0] == mtime:
        return hit[1], hit[2]

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as exc:
        raise KnowledgeUnavailable(f"cannot read {path}: {exc}") from exc

    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    _FILE_CACHE[path] = (mtime, content, sha)
    return content, sha


def load(
    agent: str,
    filenames: list[str],
    ledger: Optional[RequestLedger] = None,
    budget: int = KNOWLEDGE_CHAR_BUDGET,
) -> str:
    """Read the named references for `agent` and format them for prompt injection.

    `filenames` is expected in priority order — when the budget is exhausted the
    tail is dropped, because the selector puts the most relevant file first.
    """
    ref_dir = agent_reference_dir(agent)
    if not ref_dir or not filenames:
        return ""

    docs: list[LoadedDoc] = []
    used = 0
    for name in filenames:
        safe = os.path.basename(name)  # never let a selector escape the directory
        path = os.path.join(ref_dir, safe)
        if not os.path.isfile(path):
            # A declared file that is not on disk is a knowledge bug, not a soft miss.
            raise KnowledgeUnavailable(f"{agent}: declared reference '{safe}' is missing")

        content, sha = _read_cached(path)

        if ledger is not None and not ledger.note(sha, safe):
            # Same content already injected for this request under another name.
            print(f"[knowledge] {agent}: '{safe}' deduped (identical content already loaded)")
            continue

        if used + len(content) > budget:
            if ledger is not None:
                ledger.dropped.append((agent, safe))
            print(
                f"[knowledge] {agent}: dropped '{safe}' ({len(content)} chars) — "
                f"budget {budget} exhausted at {used}"
            )
            continue

        used += len(content)
        docs.append(LoadedDoc(filename=safe, content=content, sha=sha))

    if not docs:
        return ""

    print(
        f"[knowledge] {agent}: loaded {len(docs)} doc(s), {used} chars — "
        + ", ".join(d.filename for d in docs)
    )

    blocks = ["\n\n" + "=" * 60, "REFERENCE KNOWLEDGE", "=" * 60]
    for d in docs:
        blocks.append(f"\n--- {d.filename} ---\n{d.content}")
    return "\n".join(blocks)


# --------------------------------------------------------------------------
# Selection: which of the declared references does this task need
# --------------------------------------------------------------------------

_SELECTOR_SYSTEM = """You pick which reference documents an agent needs for one task.

You are given a task and a catalog of available documents with descriptions.
Return the documents whose content is genuinely required to do the task well,
most important first.

Rules:
- Prefer 1-3 documents. Only exceed that when the task truly spans more areas.
- Do not pick a document just because it is topically adjacent — pick it because
  the task cannot be answered correctly without what is inside it.
- If pricing, packages, or cost appear anywhere in the task, the ratecard is required.
- Return ONLY a JSON array of filenames, nothing else. Example: ["a.md","b.md"]"""


def _fallback_selection(catalog: list[ReferenceEntry], limit: int = 2) -> list[str]:
    """Used when the selector call fails. Better to inject the agent's primary
    references than to run with no knowledge at all."""
    return [e.filename for e in catalog[:limit]]


# The task is about money. Deliberately broad: a false positive costs one extra
# document in the prompt, a false negative costs a quotation invented from memory.
#
# The unaccented spellings are not padding — Vietnamese reps type without diacritics
# constantly, and gate_fields.yaml already carries the same duplication for the same
# reason ("ko biet" next to "không biết"). Only unambiguous multi-word forms are
# listed: bare "gia", "goi" and "ty" also spell "gia đình", "gọi" and "tỷ lệ", and
# matching those would drag the ratecard into every task in the system.
_PRICING_TASK_RE = re.compile(
    r"(giá|báo giá|bảng giá|chi phí|ngân sách|báo phí|"
    r"bao gia|bang gia|chi phi|ngan sach|bao phi|"
    r"ratecard|rate card|pricing|price|quotation|quote|budget|cost|"
    r"gói|package|add-?on|vat|"
    r"triệu|tỷ|tỉ|trieu|vnd|vnđ)",
    re.IGNORECASE,
)

# A catalog entry that declares itself the price source. Matched against the
# PURPOSE column of the agent's own Reference Skills List rather than a filename,
# so this keeps working if the file is renamed or another agent gains a ratecard —
# the catalog is already the declared source of truth for what a document is.
_RATECARD_PURPOSE_RE = re.compile(r"(ratecard|rate card|bảng giá|price list)", re.IGNORECASE)

# Cap on force-injected documents, so a catalog that describes several files as
# pricing-related cannot swallow the whole character budget on its own.
_MAX_MANDATORY = 2


def _mandatory_refs(task: str, catalog: list[ReferenceEntry]) -> list[str]:
    """References that must reach the prompt no matter what the selector chose.

    The selector prompt already says "if pricing appears, the ratecard is required",
    but that is an instruction to a model, and the rule this codebase runs on is that
    instruction is not enforcement — the planner is told the same kind of thing and
    ignores it often enough that the plan is post-checked in code. The ratecard is the
    single document where being ignored is worst: the agent still writes a quotation,
    it just writes one from memory, and a wrong price reaches a client looking exactly
    as confident as a right one. So the requirement is enforced here instead.
    """
    if not task or not _PRICING_TASK_RE.search(task):
        return []
    return [
        e.filename for e in catalog if e.purpose and _RATECARD_PURPOSE_RE.search(e.purpose)
    ][:_MAX_MANDATORY]


async def select(agent: str, task: str, catalog: list[ReferenceEntry]) -> list[str]:
    """Ask a cheap model which references this task needs.

    Never raises: a selector failure degrades to the agent's first declared
    references. A *read* failure is different and does raise — see load().
    """
    if not catalog:
        return []

    # Applied to EVERY return path below, including the failure ones. A selector that
    # errored or answered with garbage on a pricing task is exactly the case where the
    # ratecard is most likely to be missing and most expensive to miss.
    mandatory = _mandatory_refs(task, catalog)

    def _with_mandatory(picked: list[str]) -> list[str]:
        forced = [f for f in mandatory if f not in picked]
        if forced:
            print(f"[knowledge] {agent}: forced {forced} — pricing task, ratecard is mandatory")
        # Prepended, not appended: the character budget drops from the end of the list,
        # so the ratecard has to be at the front to survive a trim.
        return forced + picked

    # Below this many references, choosing costs more than just taking them all: the
    # selector is itself a model call, and on a rate-limited tier the extra request is
    # more expensive than the extra tokens. Only fan out when there is a real choice.
    if len(catalog) <= SELECTOR_MIN_CATALOG:
        names = [e.filename for e in catalog]
        print(f"[knowledge] {agent}: {len(names)} ref(s) declared — loading all, no selector call")
        return names

    listing = "\n".join(f"- {e.filename}: {e.purpose}" for e in catalog)
    user_msg = f"TASK:\n{task[:1500]}\n\nAVAILABLE DOCUMENTS:\n{listing}"

    try:
        import asyncio
        from functools import partial

        from llm.client import get_llm_client
        from llm.pool import LLM_POOL

        client = get_llm_client(os.getenv("KNOWLEDGE_SELECTOR_AGENT", "central_agent"))
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            LLM_POOL,
            partial(
                client.create_completion,
                messages=[
                    {"role": "system", "content": _SELECTOR_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=200,
                stream=False,
            ),
        )
        raw = (response.choices[0].message.content or "").strip()
    except Exception as exc:
        print(f"[knowledge] {agent}: selector failed ({exc}) — falling back to primary refs")
        return _with_mandatory(_fallback_selection(catalog))

    # Models like to wrap JSON in prose or fences; take the first array we find.
    match = re.search(r"\[[^\]]*\]", raw, re.DOTALL)
    if not match:
        print(f"[knowledge] {agent}: selector returned no JSON array — falling back")
        return _with_mandatory(_fallback_selection(catalog))

    try:
        picked = json.loads(match.group(0))
    except json.JSONDecodeError:
        print(f"[knowledge] {agent}: selector JSON invalid — falling back")
        return _with_mandatory(_fallback_selection(catalog))

    declared = {e.filename for e in catalog}
    valid = [os.path.basename(str(p)) for p in picked if os.path.basename(str(p)) in declared]

    if not valid:
        print(f"[knowledge] {agent}: selector picked nothing valid — falling back")
        return _with_mandatory(_fallback_selection(catalog))

    print(f"[knowledge] {agent}: selected {valid}")
    return _with_mandatory(valid)
