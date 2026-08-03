"""
FigmaWireframeSkill
-------------------
Turns an assembled proposal into a machine-renderable low-fidelity wireframe spec that the
AdtimaBox Figma plugin (figma-plugin/) draws with the Figma Plugin API.

On-demand only. This skill is NOT in any plan group and the planner never selects it — it is
invoked by `POST /figma/wireframe/{session_id}` when the rep presses "Vẽ Wireframe trên
Figma" after a proposal exists. Running it inside the proposal pipeline would add a
serialised LLM call (LLM_MAX_CONCURRENCY=1) to every proposal turn for an artifact most turns
never ask for.

Payload keys:
  spec         — {"meta": {...}, "screens": [...]}, already validated against the closed
                 block vocabulary. `screens` may be empty: that is the correct answer for a
                 proposal with no UI to draw, and the caller reports it as such.
  screen_count — len(spec["screens"])
"""

from __future__ import annotations

import json
import os
from typing import Any

from skills.base import BaseSkill, SkillContext, SkillOutput, extract_json_block, loads_lenient

_HERE = os.path.dirname(os.path.abspath(__file__))
_SKILL_MD = os.path.join(_HERE, "..", "..", "agents", "figma_wireframe_agent", "SKILL.md")

# Bump whenever the block vocabulary, the screen-count guidance or the reference knowledge
# changes in a way that would produce a different spec from the same proposal.
#
# main.py fingerprints the proposal to avoid spending an LLM call when a rep presses the
# button twice. Keyed on the proposal alone, that cache also survives an upgrade of this
# skill: after the vocabulary went 9 kinds → 25, every existing session kept serving its
# parked 9-kind spec, and because the cache short-circuits before the skill runs there was no
# log line either — the deploy looked like it had done nothing. The version is part of the
# fingerprint so a skill upgrade invalidates parked specs the same way an edited proposal does.
SPEC_VERSION = 2

# The renderer in figma-plugin/code.js knows exactly these 25 kinds. A kind outside this set
# draws as a grey box labelled with the kind name — technically survivable, but it wastes a
# screen region, so an unknown kind is dropped here instead of shipped to the plugin.
# SKILL.md declares the same 25; the two lists cannot drift without the spec silently losing
# blocks. The first nine were the original vocabulary; the rest were added because a nine-block
# set could only express "heading + list + button", which is what made every screen look the
# same regardless of what the journey actually described.
_BLOCK_KINDS = frozenset({
    # chrome & structure
    "appbar", "tabbar", "tabs", "section",
    # identity & progress
    "hero", "stats", "progress",
    # content
    "text", "banner", "carousel", "card", "list", "grid", "chips",
    "voucher", "qr", "steps", "note", "empty",
    # input & action
    "field", "toggle", "timeslot", "cta", "sheet",
    # escape hatch
    "placeholder",
})
_PLATFORMS = frozenset({"miniapp", "zns", "oa"})

# A ZNS is a fixed template Zalo renders in the chat list: no navigation, no scrolling
# collection, no input. The renderer drops these too, but dropping them here as well keeps the
# stored spec honest about what will actually be drawn. Mirrors the table in
# zns-oa-templates.md.
_ZNS_FORBIDDEN = frozenset({
    "tabbar", "tabs", "list", "grid", "carousel", "chips",
    "field", "toggle", "timeslot", "sheet", "hero", "empty",
})
# An OA message is a chat bubble. It may deliver a voucher, but it is not an app screen.
_OA_FORBIDDEN = frozenset({
    "tabbar", "tabs", "grid", "timeslot", "toggle", "sheet", "hero", "field",
})

# Literal placeholder strings a model reaches for when it has nothing real to say. The
# wireframe's whole value is that an unspecified region reads as unspecified — a field
# containing the text "TBD" reads as a design decision instead, so these are dropped and the
# renderer's own skip-if-absent behaviour takes over.
_JUNK_VALUES = frozenset({"tbd", "n/a", "na", "none", "null", "undefined", "-", "...", "[]"})

# Below this the input cannot be a proposal — same guard and same reasoning as
# wireframe_designer's _MIN_PROPOSAL_CHARS: a brief-only input produces a confident
# hallucinated app, which is worse than an honest refusal.
_MIN_PROPOSAL_CHARS = 1200


def _clean_str(value: Any) -> str:
    """A usable string, or "" — which callers treat as absent."""
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text or text.lower() in _JUNK_VALUES:
        return ""
    # A model that starts inventing often emits the bracket form verbatim from the schema.
    if text.startswith("[") and text.endswith("]"):
        return ""
    return text


def _clean_fraction(value: Any) -> float | None:
    """A progress value in 0..1, or None — which means "draw no bar".

    Accepts the percentage form too: a model given "750 of 1000 points" reaches for 75 about as
    often as 0.75, and a bar drawn at 75x full width is indistinguishable from a broken one.
    Anything non-numeric (including the string "abc" and bools) is None rather than 0 — an
    unparseable progress is unknown progress, not zero progress, and a bar pinned empty reads
    as a real figure.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):  # NaN / inf
        return None
    # Only a *whole* number above 1 is read as a percentage. A fractional 1.7 is an
    # out-of-range fraction, not "1.7%" — reading it as a percentage turned a slightly-wrong
    # value into a bar at 2% of full, which looks like a real figure rather than a mistake.
    if number > 1 and number == int(number):
        number /= 100.0
    return max(0.0, min(1.0, number))


def _clean_index(value: Any, length: int) -> int:
    """A 0-based index into a list of `length`, clamped. 0 when absent or unusable."""
    if isinstance(value, bool) or not isinstance(value, int) or length <= 0:
        return 0
    return max(0, min(length - 1, value))


def _clean_items(raw: Any, limit: int) -> list[dict]:
    """The dict entries of an items list, capped. Non-dicts dropped."""
    if not isinstance(raw, list):
        return []
    return [i for i in raw if isinstance(i, dict)][:limit]


def _clean_labels(raw: Any, limit: int) -> list[str]:
    """A list of plain string labels, junk and blanks removed, capped."""
    if not isinstance(raw, list):
        return []
    return [s for s in (_clean_str(i) for i in raw) if s][:limit]


def _clean_rows(raw: Any, limit: int = 4) -> list[dict]:
    """label/value pairs — the figures a user verifies. Dropped when both sides are empty."""
    rows = []
    for row in _clean_items(raw, limit):
        label, value = _clean_str(row.get("label")), _clean_str(row.get("value"))
        if label or value:
            rows.append({"label": label, "value": value})
    return rows


def _clean_block(raw: Any) -> dict | None:
    """One block, keeping only the fields its kind actually uses. None if unrenderable."""
    if not isinstance(raw, dict):
        return None
    kind = _clean_str(raw.get("kind")).lower()
    if kind not in _BLOCK_KINDS:
        return None

    block: dict[str, Any] = {"kind": kind}

    if kind == "appbar":
        block["title"] = _clean_str(raw.get("title"))
        block["back"] = bool(raw.get("back"))
        return block

    if kind == "banner":
        block["text"] = _clean_str(raw.get("text"))
        emoji = _clean_str(raw.get("emoji"))
        if emoji:
            block["emoji"] = emoji
        # A banner with no label is still a meaningful dashed region — keep it.
        return block

    if kind == "text":
        text = _clean_str(raw.get("text"))
        if not text:
            return None  # an empty text block occupies space and says nothing
        style = _clean_str(raw.get("style")).lower()
        block["text"] = text
        block["style"] = style if style in ("heading", "body", "caption") else "body"
        return block

    if kind == "card":
        rows = _clean_rows(raw.get("rows"))
        title, subtitle = _clean_str(raw.get("title")), _clean_str(raw.get("subtitle"))
        if not (title or subtitle or rows):
            return None
        block["title"], block["subtitle"], block["rows"] = title, subtitle, rows
        return block

    if kind in ("list", "grid", "carousel"):
        # Same item shape for all three; only `list` carries a trailing `meta` figure, and only
        # `list` has a section title (a grid's heading is a separate `section` block).
        items = []
        for item in _clean_items(raw.get("items"), 6 if kind == "grid" else 4):
            item_title = _clean_str(item.get("title"))
            if not item_title:
                continue
            entry = {"title": item_title, "sub": _clean_str(item.get("sub"))}
            emoji = _clean_str(item.get("emoji"))
            if emoji:
                entry["emoji"] = emoji
            if kind == "list":
                meta = _clean_str(item.get("meta"))
                if meta:
                    entry["meta"] = meta
            items.append(entry)
        if not items:
            # An empty collection is exactly the case the placeholder block exists for: the
            # proposal implied a collection without naming its contents.
            fallback = _clean_str(raw.get("title")) or "Danh sách"
            return {"kind": "placeholder", "label": fallback}
        block["items"] = items
        if kind == "list":
            block["title"] = _clean_str(raw.get("title"))
        return block

    if kind == "hero":
        # Every field is optional and the block is still meaningful with none of them — a member
        # header with an avatar and empty slots is a real region. Kept even when bare.
        block["name"] = _clean_str(raw.get("name"))
        block["tier"] = _clean_str(raw.get("tier"))
        block["points"] = _clean_str(raw.get("points"))
        progress = _clean_fraction(raw.get("progress"))
        if progress is not None:
            block["progress"] = progress
            block["progress_label"] = _clean_str(raw.get("progress_label"))
        return block

    if kind == "stats":
        items = []
        for item in _clean_items(raw.get("items"), 4):
            value, label = _clean_str(item.get("value")), _clean_str(item.get("label"))
            if value or label:
                items.append({"value": value, "label": label})
        if not items:
            return None
        block["items"] = items
        return block

    if kind == "progress":
        progress = _clean_fraction(raw.get("value"))
        label = _clean_str(raw.get("label"))
        # Unlike hero's bar, this block IS the bar — with no figure there is nothing to draw,
        # so it degrades to the labelled placeholder rather than an empty track.
        if progress is None:
            return {"kind": "placeholder", "label": label or "Tiến độ"} if label else None
        block["value"] = progress
        block["label"] = label
        block["caption"] = _clean_str(raw.get("caption"))
        return block

    if kind == "chips":
        items = _clean_labels(raw.get("items"), 5)
        if not items:
            return None
        block["items"] = items
        block["active"] = _clean_index(raw.get("active"), len(items))
        return block

    if kind == "voucher":
        value = _clean_str(raw.get("value"))
        title = _clean_str(raw.get("title"))
        if not (value or title):
            return None
        block["value"], block["title"] = value, title
        for field in ("condition", "expiry", "code"):
            text = _clean_str(raw.get(field))
            if text:
                block[field] = text
        return block

    if kind == "qr":
        # A QR region with no code is the honest form when the proposal describes a counter scan
        # without naming a code format (wireframe-fidelity.md) — so the block survives bare.
        block["label"] = _clean_str(raw.get("label")) or "Mã QR"
        for field in ("code", "caption"):
            text = _clean_str(raw.get(field))
            if text:
                block[field] = text
        return block

    if kind == "steps":
        items = []
        for item in _clean_items(raw.get("items"), 5):
            label = _clean_str(item.get("label"))
            if not label:
                continue
            items.append({
                "label": label,
                "sub": _clean_str(item.get("sub")),
                "done": bool(item.get("done")),
            })
        if not items:
            return None
        block["items"] = items
        return block

    if kind == "note":
        text = _clean_str(raw.get("text"))
        if not text:
            return None
        tone = _clean_str(raw.get("tone")).lower()
        block["text"] = text
        block["tone"] = tone if tone in ("info", "warning") else "info"
        return block

    if kind == "empty":
        block["label"] = _clean_str(raw.get("label")) or "Chưa có dữ liệu"
        emoji = _clean_str(raw.get("emoji"))
        if emoji:
            block["emoji"] = emoji
        return block

    if kind == "field":
        label = _clean_str(raw.get("label"))
        if not label:
            return None
        block["label"] = label
        block["placeholder"] = _clean_str(raw.get("placeholder"))
        field_type = _clean_str(raw.get("type")).lower()
        block["type"] = (
            field_type if field_type in ("text", "phone", "select", "date", "textarea") else "text"
        )
        return block

    if kind == "toggle":
        label = _clean_str(raw.get("label"))
        if not label:
            return None
        block["label"] = label
        block["sub"] = _clean_str(raw.get("sub"))
        block["on"] = bool(raw.get("on"))
        return block

    if kind == "timeslot":
        items = _clean_labels(raw.get("items"), 9)
        if not items:
            return {"kind": "placeholder", "label": _clean_str(raw.get("label")) or "Chọn giờ"}
        block["label"] = _clean_str(raw.get("label"))
        block["items"] = items
        block["active"] = _clean_index(raw.get("active"), len(items))
        return block

    if kind == "cta":
        text = _clean_str(raw.get("text"))
        if not text:
            return None
        variant = _clean_str(raw.get("variant")).lower()
        block["text"] = text
        block["variant"] = variant if variant in ("primary", "secondary") else "primary"
        return block

    if kind == "sheet":
        title = _clean_str(raw.get("title"))
        rows = _clean_rows(raw.get("rows"))
        cta = _clean_str(raw.get("cta"))
        if not (title or rows or cta):
            return None
        block["title"], block["rows"], block["cta"] = title, rows, cta
        return block

    if kind in ("tabbar", "tabs"):
        items = _clean_labels(raw.get("items"), 4)
        if not items:
            return None
        block["items"] = items
        return block

    if kind == "section":
        title = _clean_str(raw.get("title"))
        if not title:
            return None
        block["title"] = title
        block["action"] = _clean_str(raw.get("action"))
        return block

    # placeholder
    block["label"] = _clean_str(raw.get("label")) or "Khu vực chưa xác định"
    return block


def _clean_screen(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    blocks = [b for b in (_clean_block(b) for b in raw.get("blocks") or []) if b]
    platform = _clean_str(raw.get("platform")).lower()
    if platform not in _PLATFORMS:
        platform = "miniapp"

    # SKILL.md forbids these per platform — a notification has no navigation, no scrolling
    # collection and no input; an OA message is a chat bubble, not an app screen. Enforced in
    # code because the constraint is structural: the plugin would happily draw a tabbar into a
    # ZNS frame and the result misrepresents what the platform can do.
    forbidden = _ZNS_FORBIDDEN if platform == "zns" else (
        _OA_FORBIDDEN if platform == "oa" else frozenset()
    )
    if forbidden:
        dropped = sorted({b["kind"] for b in blocks if b["kind"] in forbidden})
        if dropped:
            # Worth a line: a rep asking why a ZNS looks emptier than the proposal implied has
            # no other way to find out that blocks were removed rather than never generated.
            print(f"[figma_wireframe] {platform} screen: dropped {dropped}")
        blocks = [b for b in blocks if b["kind"] not in forbidden]

    # Screens are only worth drawing if something is on them. A screen of pure chrome (appbar,
    # bottom nav, a section heading over nothing) is not a wireframe of anything.
    if not any(b["kind"] not in ("appbar", "tabbar", "tabs", "section") for b in blocks):
        return None

    return {
        "name": _clean_str(raw.get("name")) or "Màn hình",
        "platform": platform,
        "note": _clean_str(raw.get("note")),
        "blocks": blocks,
    }


def _clean_spec(raw: Any, fallback_brand: str) -> dict:
    meta_raw = raw.get("meta") if isinstance(raw, dict) else None
    meta_raw = meta_raw if isinstance(meta_raw, dict) else {}
    screens_raw = raw.get("screens") if isinstance(raw, dict) else None

    screens = [s for s in (_clean_screen(s) for s in screens_raw or []) if s]
    lang = _clean_str(meta_raw.get("lang")).lower()

    return {
        "meta": {
            "brand": _clean_str(meta_raw.get("brand")) or fallback_brand,
            "product": _clean_str(meta_raw.get("product")) or "Zalo Mini App",
            "lang": lang if lang in ("vi", "en") else "vi",
            "note": _clean_str(meta_raw.get("note")),
        },
        "screens": screens,
    }


class FigmaWireframeSkill(BaseSkill):
    def __init__(self):
        super().__init__(
            name="figma_wireframe",
            description=(
                "Builds a low-fidelity Zalo Mini App / ZNS / OA wireframe spec from an "
                "assembled proposal, for the AdtimaBox Figma plugin to draw. On-demand only "
                "— triggered by the rep, never planned."
            ),
            model_key="MODEL_FIGMA_WIREFRAME",
            skill_md_path=_SKILL_MD,
        )

    async def execute(self, context: SkillContext) -> SkillOutput:
        proposal = (context.previous_outputs.get("proposal_assembler") or {}).get("content", "")
        if len(proposal) < _MIN_PROPOSAL_CHARS:
            return SkillOutput(
                skill=self.name,
                status="FAILED",
                payload={},
                summary=(
                    "Chưa có proposal đủ chi tiết để dựng wireframe — cần chạy tạo proposal "
                    "trước khi vẽ Figma."
                ),
                content="",
            )

        brand = ""
        if context.brief and context.brief.industry:
            brand = context.brief.industry

        ref_context = await self.retrieve_reference_context(context, top_k=3)
        org_rules = await self._fetch_org_rules()
        system = self._build_system_prompt(context.constraints, org_rules)
        if ref_context:
            system = system + ref_context

        user_msg = (
            f"{context.task}\n\n## PROPOSAL DOCUMENT\n{proposal}\n\n"
            "Emit the wireframe spec JSON now. Start your response with {"
        )

        try:
            # `history` is deliberately empty: this call emits JSON only, and eight turns of
            # Vietnamese conversation in front of that prompt is the reliable way to get a
            # chatty preamble before the opening brace.
            content, truncated = await self._call_llm(
                system=system,
                user_msg=user_msg,
                history=[],
                # 6000 was sized against the original "aim for 3-6 screens, 4-7 blocks" brief.
                # The target is now 6-12 screens of 5-9 blocks from a 25-kind vocabulary, and a
                # rich screen serialises to 400-700 tokens — so a full journey needs upwards of
                # 8k before Gemini's own reasoning budget is counted. Truncation here is not a
                # partial result: the JSON is cut mid-object and the whole spec fails to parse,
                # which is why this is generous rather than tight.
                max_tokens=16000,
                temperature=0.2,
            )
        except Exception as e:
            return SkillOutput(
                skill=self.name,
                status="FAILED",
                payload={"error": str(e)},
                summary=f"Skill {self.name} failed: {e}",
                content="",
            )

        try:
            raw = loads_lenient(extract_json_block(content))
        except (json.JSONDecodeError, ValueError) as e:
            # Truncation is the likeliest cause of an unparseable spec at this size, so say
            # which it was — "the model was cut off" and "the model wrote bad JSON" need
            # different responses from the rep.
            reason = "bị cắt do quá dài" if truncated else "sai định dạng JSON"
            print(f"[figma_wireframe] spec parse failed ({reason}): {e}")
            return SkillOutput(
                skill=self.name,
                status="FAILED",
                payload={"error": str(e)},
                summary=f"Không dựng được wireframe: kết quả {reason}. Thử lại sau ít phút.",
                content="",
            )

        spec = _clean_spec(raw, fallback_brand=brand or "Client")
        screens = spec["screens"]

        if not screens:
            # The honest empty result, per wireframe-fidelity.md: a proposal whose solution
            # section describes no user-facing surface has nothing to wireframe, and saying
            # so beats drawing an invented app.
            print("[figma_wireframe] no drawable screens in this proposal")
            return SkillOutput(
                skill=self.name,
                status="FAILED",
                payload={"spec": spec, "screen_count": 0},
                summary=(
                    "Proposal này chưa mô tả màn hình/giao diện nào để vẽ wireframe. Bổ sung "
                    "hành trình người dùng ở Section 3 rồi thử lại."
                ),
                content="",
            )

        kinds = sorted({b["kind"] for s in screens for b in s["blocks"]})
        total_blocks = sum(len(s["blocks"]) for s in screens)
        print(
            f"[figma_wireframe] {len(screens)} screen(s), {total_blocks} block(s) "
            f"(avg {total_blocks / len(screens):.1f}/screen), "
            f"platforms={sorted({s['platform'] for s in screens})}, kinds={kinds}"
        )
        # The two failure modes wireframe-fidelity.md names, both invisible in the output
        # itself: a journey compressed into too few screens, and screens built from only the
        # generic blocks. Neither is worth failing the turn over, but a log line is what makes
        # "the model ignored the vocabulary again" diagnosable from outside.
        if len(screens) < 5:
            print(f"[figma_wireframe] WARN thin journey: {len(screens)} screen(s), expected 6-12")
        _RICH = {"hero", "voucher", "qr", "grid", "steps", "carousel", "chips", "progress", "stats"}
        if not _RICH & set(kinds):
            print(f"[figma_wireframe] WARN flat output: no rich block used, only {kinds}")

        manifest_lines = [
            f"  {i}. [{s['platform']}] {s['name']} — {len(s['blocks'])} block(s)"
            for i, s in enumerate(screens, 1)
        ]
        return SkillOutput(
            skill=self.name,
            status="PARTIAL" if truncated else "COMPLETE",
            payload={"spec": spec, "screen_count": len(screens)},
            summary=f"Đã dựng wireframe spec ({len(screens)} màn hình) cho Figma",
            content=(
                f"FIGMA WIREFRAME SPEC BUILT — {len(screens)} screen(s) for "
                f"{spec['meta']['brand']} on {spec['meta']['product']}.\n"
                "These are the actual screens in the spec; describe THESE and nothing else.\n"
                + "\n".join(manifest_lines)
            ),
        )
