"""
KB Ingestion Pipeline
=====================
Ingests documents from various sources into the knowledge base.
Supports pluggable loaders (MD now; PDF/CSV/PNG = future).

Documents are ingested per-agent from agents/<name>/knowledge/*.md
"""

import os
import asyncio
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class IngestedDocument:
    """Result of a document ingestion."""

    doc_id: str
    source: str
    content: str
    metadata: dict[str, Any]
    success: bool
    error: Optional[str] = None


class BaseLoader:
    """Base class for document loaders."""

    async def load(self, path: str) -> list[IngestedDocument]:
        """Load documents from a path. Returns list of ingested documents."""
        raise NotImplementedError


class MarkdownLoader(BaseLoader):
    """
    Loads Markdown files.
    Splits on headers to create multiple documents per file.
    """

    def __init__(self, max_chunk_size: int = 2000):
        """
        Initialize the markdown loader.

        Args:
            max_chunk_size: Maximum characters per chunk
        """
        self.max_chunk_size = max_chunk_size

    async def load(self, path: str) -> list[IngestedDocument]:
        """Load a markdown file and split into chunks."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return [
                IngestedDocument(
                    doc_id="",
                    source=path,
                    content="",
                    metadata={},
                    success=False,
                    error=str(e),
                )
            ]

        # Split by headers (## or ###)
        chunks = self._split_by_headers(content)

        documents = []
        source_name = os.path.basename(path)

        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue

            documents.append(
                IngestedDocument(
                    doc_id=f"{source_name}_{i}",
                    source=source_name,
                    content=chunk.strip(),
                    metadata={
                        "source": source_name,
                        "chunk": i,
                        "total_chunks": len(chunks),
                        "type": "markdown",
                    },
                    success=True,
                )
            )

        return documents

    def _split_by_headers(self, content: str) -> list[str]:
        """Split content by markdown headers."""
        import re

        # Split on ## or ### headers
        parts = re.split(r"(?=^#{2,3}\s)", content, flags=re.MULTILINE)

        chunks = []
        current_chunk = ""

        for part in parts:
            if not part.strip():
                continue

            # Check if adding this would exceed max size
            if len(current_chunk) + len(part) > self.max_chunk_size and current_chunk:
                chunks.append(current_chunk)
                current_chunk = part
            else:
                current_chunk += "\n\n" + part if current_chunk else part

        # Add remaining
        if current_chunk:
            chunks.append(current_chunk)

        # If no chunks created, return whole content
        return chunks if chunks else [content]


class PlainTextLoader(BaseLoader):
    """Loads plain text files."""

    async def load(self, path: str) -> list[IngestedDocument]:
        """Load a plain text file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return [
                IngestedDocument(
                    doc_id="",
                    source=path,
                    content="",
                    metadata={},
                    success=False,
                    error=str(e),
                )
            ]

        source_name = os.path.basename(path)
        return [
            IngestedDocument(
                doc_id=source_name,
                source=source_name,
                content=content,
                metadata={"source": source_name, "type": "text"},
                success=True,
            )
        ]


# Loader registry
LOADERS = {
    ".md": MarkdownLoader(),
    ".markdown": MarkdownLoader(),
    ".txt": PlainTextLoader(),
}


def get_loader(extension: str) -> Optional[BaseLoader]:
    """Get the appropriate loader for a file extension."""
    return LOADERS.get(extension.lower())


async def ingest_agent_knowledge(
    agent_name: str,
    kb_repo: Any,
    knowledge_dir: Optional[str] = None,
) -> dict[str, Any]:
    """
    Ingest all knowledge files for a specific agent.

    Args:
        agent_name: Name of the agent
        kb_repo: KBRepo instance to store documents
        knowledge_dir: Override knowledge directory path

    Returns:
        Summary of ingestion results
    """
    # Default to agents/<name>/knowledge
    base_dir = Path(__file__).parent.parent / "agents" / agent_name / "knowledge"

    if knowledge_dir:
        base_dir = Path(knowledge_dir)

    if not base_dir.exists():
        return {
            "agent": agent_name,
            "status": "skipped",
            "reason": f"Knowledge directory not found: {base_dir}",
            "documents_ingested": 0,
        }

    # Find all supported files
    files = []
    for ext in LOADERS.keys():
        files.extend(base_dir.glob(f"*{ext}"))

    if not files:
        return {
            "agent": agent_name,
            "status": "skipped",
            "reason": "No knowledge files found",
            "documents_ingested": 0,
        }

    # Ingest each file
    total_ingested = 0
    errors = []

    for file_path in files:
        loader = get_loader(file_path.suffix)
        if not loader:
            continue

        # Load document chunks
        documents = await loader.load(str(file_path))

        # Add to KB
        for doc in documents:
            if doc.success:
                try:
                    await kb_repo.add_document(
                        content=doc.content,
                        metadata={
                            **doc.metadata,
                            "agent": agent_name,
                            "file": str(file_path),
                        },
                    )
                    total_ingested += 1
                except Exception as e:
                    errors.append(f"{file_path}: {str(e)}")

    return {
        "agent": agent_name,
        "status": "success" if total_ingested > 0 else "error",
        "files_found": len(files),
        "documents_ingested": total_ingested,
        "errors": errors if errors else None,
    }


async def ingest_all_agents(kb_repo: Any) -> list[dict[str, Any]]:
    """
    Ingest knowledge for all agents.

    Args:
        kb_repo: KBRepo instance

    Returns:
        List of ingestion results per agent
    """
    # Get list of agent directories
    agents_dir = Path(__file__).parent.parent / "agents"

    if not agents_dir.exists():
        return []

    results = []

    for agent_dir in agents_dir.iterdir():
        if not agent_dir.is_dir():
            continue

        # Skip non-agent directories
        if agent_dir.name.startswith("_") or agent_dir.name in ["__pycache__"]:
            continue

        # Check if knowledge directory exists
        knowledge_dir = agent_dir / "knowledge"
        if not knowledge_dir.exists():
            continue

        result = await ingest_agent_knowledge(agent_dir.name, kb_repo)
        results.append(result)

    return results


async def search_knowledge(
    query: str,
    agent_name: Optional[str] = None,
    top_k: int = 5,
) -> list[Any]:
    """
    Search the knowledge base.

    Args:
        query: Search query
        agent_name: Optional agent to filter by
        top_k: Number of results

    Returns:
        List of SearchResult objects
    """
    from repos.kb_repo import get_kb_repo

    kb = get_kb_repo()

    # Build filters
    filters = None
    if agent_name:
        filters = {"agent": agent_name}

    return await kb.search(query, top_k=top_k, filters=filters)


# CLI for manual ingestion
if __name__ == "__main__":
    import sys

    async def main():
        from repos.kb_repo import get_kb_repo

        kb = get_kb_repo()

        if len(sys.argv) > 1:
            # Ingest specific agent
            agent_name = sys.argv[1]
            result = await ingest_agent_knowledge(agent_name, kb)
            print(f"Ingestion result: {result}")
        else:
            # Ingest all agents
            results = await ingest_all_agents(kb)
            print("Ingestion results:")
            for r in results:
                print(f"  {r['agent']}: {r['status']} - {r.get('documents_ingested', 0)} docs")

    asyncio.run(main())