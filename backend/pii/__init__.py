"""PII masking — a system component that runs before any model call (BRD §3, §4[A])."""

from pii.masking import MaskResult, SessionMasker, forget_session, get_masker

__all__ = ["MaskResult", "SessionMasker", "forget_session", "get_masker"]
