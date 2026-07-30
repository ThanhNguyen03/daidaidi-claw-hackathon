"""
Slide extraction for the Adtima-corporate PPTX template (pptx_corporate.py).

Independent from html_deck.py's extraction (different schema, different section
scheme — see agents/wireframe_designer_agent/PPTX_CORPORATE_SCHEMA.md), but reuses
its proven JSON-repair/salvage plumbing rather than duplicating it: the
bracket-balanced `_find_json_array`/`_salvage_json_objects` helpers are imported
from html_deck.py, and `strip_think_blocks`/`extract_json_block`/`repair_json_escapes`
from skills/base.py.
"""

from __future__ import annotations

import asyncio
import json
import os
from functools import partial

_SCHEMA_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "agents", "wireframe_designer_agent", "PPTX_CORPORATE_SCHEMA.md",
    )
)


def _load_extract_system(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"[CorporatePPTX] extraction prompt not found at {path!r}. PPTX slide "
            "extraction cannot run without it — check that agents/"
            "wireframe_designer_agent/PPTX_CORPORATE_SCHEMA.md exists."
        )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if not content.strip():
        raise ValueError(f"[CorporatePPTX] extraction prompt at {path!r} is empty.")
    return content


_EXTRACT_SYSTEM = _load_extract_system(_SCHEMA_PATH)
_EXTRACT_MAX_TOKENS = int(os.getenv("DECK_EXTRACT_MAX_TOKENS", "24000"))

_REQUIRED_FIELDS = {
    "deck_meta": [],            # optional cover campaign_line, no required fields
    "executive_summary": [],   # validated below: headline or summary
    "client_requirements": [],  # validated below: at least one of the 4 quadrants
    "solution_package": [],     # validated below: addons or package.name
    "user_journey": ["steps"],
    "solution_flowchart": ["nodes"],
    "touchpoints_table": ["rows"],
    "compliance": ["verdict"],
    "quotation": [],            # validated below: line_items or total
    "quotation_alternative": [],
    "case_study": ["cases"],
    "next_steps": [],           # validated below: weeks, decisions, or tech_items
}

# Sections gated behind compliance: the source proposal (proposal_assembler's
# 7-section template) omits Investment and Next Steps entirely when compliance
# is BLOCKED — the prompt is told to match that, but instruction is not
# enforcement (see gate.py's whole reason for existing), so it's re-checked here
# against whatever verdict the extraction actually returned.
_BLOCKED_GATED_TYPES = {"quotation", "quotation_alternative", "next_steps"}


def _validate_slides(slides: list) -> list:
    """Drop slides missing required fields or with empty content — mirrors
    html_deck.py's _validate_slides for this schema's types."""
    valid = []
    dropped: list[str] = []
    compliance = next((s for s in slides if s.get("type") == "compliance"), None)
    blocked = bool(compliance and (compliance.get("verdict") or "").upper() == "BLOCKED")
    for s in slides:
        t = s.get("type")
        if t not in _REQUIRED_FIELDS:
            dropped.append(f"{t}(unknown type)")
            continue
        if blocked and t in _BLOCKED_GATED_TYPES:
            dropped.append(f"{t}(skipped — compliance verdict is BLOCKED)")
            continue
        missing = [f for f in _REQUIRED_FIELDS[t] if not s.get(f)]
        if missing:
            dropped.append(f"{t}(missing {','.join(missing)})")
            continue
        if t == "executive_summary" and not (s.get("headline") or s.get("summary")):
            dropped.append("executive_summary(no headline or summary)")
            continue
        if t == "client_requirements" and not any(
            s.get(k) for k in ("current_state", "core_pain", "desired_outcome", "gap")
        ):
            dropped.append("client_requirements(all quadrants empty)")
            continue
        if t == "solution_package" and not (s.get("addons") or (s.get("package") or {}).get("name")):
            dropped.append("solution_package(no addons or package name)")
            continue
        if t == "solution_flowchart" and not any(n.get("decision") for n in (s.get("nodes") or [])):
            # The prompt says "only emit when there's a real branch, skip if linear"
            # — but that's instruction, not enforcement, and the model doesn't
            # reliably follow it: measured output produced a flowchart with the
            # exact same steps as user_journey and zero decision nodes, i.e. a
            # duplicate slide dressed up as a different type. A flowchart with no
            # decision node isn't branching, so drop it here instead of trusting
            # the prompt alone (same principle as gate.py: instruction is not
            # enforcement).
            dropped.append("solution_flowchart(no decision node — not actually branching, duplicates user_journey)")
            continue
        if t in ("quotation", "quotation_alternative") and not (s.get("line_items") or s.get("total")):
            dropped.append(f"{t}(no line_items or total)")
            continue
        if t == "next_steps" and not (s.get("weeks") or s.get("decisions") or s.get("tech_items")):
            dropped.append("next_steps(no weeks, decisions, or tech_items)")
            continue
        valid.append(s)
    if dropped:
        print(f"[CorporatePPTX] validation dropped {len(dropped)}: {dropped}")
    return valid


async def _extract_slides(proposal_text: str, brief: dict, attempt: int = 0) -> list[dict]:
    from llm.client import get_llm_client
    from llm.pool import LLM_POOL
    from skills.base import strip_think_blocks, extract_json_block, repair_json_escapes
    from generation.html_deck import _find_json_array, _salvage_json_objects

    client = get_llm_client("deck_extractor")
    brand_hint = (brief or {}).get("industry", "")
    trimmed = proposal_text[:45000] if attempt > 0 else proposal_text[:80000]

    loop = asyncio.get_running_loop()
    resp = await loop.run_in_executor(
        LLM_POOL,
        partial(
            client.create_completion,
            messages=[
                {"role": "system", "content": _EXTRACT_SYSTEM},
                {"role": "user", "content": f"Brand context: {brand_hint}\n\nProposal:\n{trimmed}"},
            ],
            temperature=0.0,
            max_tokens=_EXTRACT_MAX_TOKENS,
            stream=False,
        ),
    )
    choice = resp.choices[0]
    raw = choice.message.content or ""
    finish = getattr(choice, "finish_reason", None)
    completion_tokens = getattr(getattr(resp, "usage", None), "completion_tokens", None)
    raw = strip_think_blocks(raw)
    raw = extract_json_block(raw)
    raw = _find_json_array(raw)
    print(
        f"[CorporatePPTX] attempt {attempt+1} finish={finish} "
        f"completion_tokens={completion_tokens} raw ({len(raw)} chars): {raw[:300]}"
    )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raw = repair_json_escapes(raw)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = []
        if data:
            print(f"[CorporatePPTX] attempt {attempt+1}: parsed after escape repair ({e})")
        else:
            data = _salvage_json_objects(raw)
            if not data:
                raise
            print(
                f"[CorporatePPTX] attempt {attempt+1}: array unparseable ({e}) — "
                f"salvaged {len(data)} complete slide(s) from it"
            )
    if not isinstance(data, list) or not data:
        print(f"[CorporatePPTX] attempt {attempt+1}: empty/invalid list")
        return []
    validated = _validate_slides(data)
    if not validated:
        print(f"[CorporatePPTX] attempt {attempt+1}: {len(data)} slides parsed but 0 passed validation")
        return []
    print(f"[CorporatePPTX] attempt {attempt+1}: {len(validated)} valid slides {[s.get('type') for s in validated]}")
    return validated


async def extract_pptx_slides(proposal_text: str, brief: dict) -> list[dict]:
    """Try extraction twice, then give up empty — the caller (wireframe_designer
    skill) decides what an empty content-slide list means, same as html_deck.py."""
    slides: list[dict] = []
    for attempt in range(2):
        try:
            slides = await _extract_slides(proposal_text, brief, attempt)
            if slides:
                break
        except Exception as e:
            print(f"[CorporatePPTX] Extraction attempt {attempt+1} failed: {e}")

    # deck_meta isn't a renderable slide type — pull its campaign_line into the
    # cover and drop it from the list so pptx_corporate.py never sees it.
    deck_meta = next((s for s in slides if s.get("type") == "deck_meta"), None)
    slides = [s for s in slides if s.get("type") != "deck_meta"]

    brief_dict = brief or {}
    # Brief (schemas/state.py) has no company_name/date/track fields — company_name
    # and track are consistent with html_deck.py's same fallback for this same gap;
    # created_at is real data the model actually has, unlike a "date" field it doesn't.
    created_at = brief_dict.get("created_at", "")
    cover = {
        "type": "cover",
        "brand": brief_dict.get("company_name") or brief_dict.get("industry", "Brand"),
        "industry": brief_dict.get("industry", ""),
        "campaign_line": (deck_meta or {}).get("campaign_line", ""),
        "date": created_at[:10] if isinstance(created_at, str) else "",
        "track": brief_dict.get("track", "B2C"),
        "prepared_by": "AdtimaBox Sales Team",
    }
    closing = {
        "type": "closing",
        "brand": cover["brand"],
        "date": cover["date"],
        "prepared_by": "AdtimaBox",
    }
    return [cover, *slides, closing]
