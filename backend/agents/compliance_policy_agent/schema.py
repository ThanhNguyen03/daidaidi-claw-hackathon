"""
Compliance Agent Schemas
========================
Defines compliance review payloads for the migrated compliance policy agent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ComplianceFinding(BaseModel):
    severity: Literal["block", "warn", "info"] = Field(..., description="Severity of the finding")
    policy_ref: str = Field(..., description="Reference to the policy being checked")
    message: str = Field(..., description="Human-readable finding message")
    suggestion: Optional[str] = Field(None, description="Suggested compliant alternative")
    details: Optional[dict[str, Any]] = Field(None, description="Additional details about the finding")


class CompliancePayload(BaseModel):
    findings: list[ComplianceFinding] = Field(default_factory=list, description="List of compliance findings")
    overall: Literal["ok", "warn", "block"] = Field("ok", description="Overall compliance status")
    summary: str = Field("", description="Summary of compliance review")

    def has_blocking(self) -> bool:
        return any(f.severity == "block" for f in self.findings)

    def has_warnings(self) -> bool:
        return any(f.severity == "warn" for f in self.findings)

    def get_blocking_findings(self) -> list[ComplianceFinding]:
        return [f for f in self.findings if f.severity == "block"]

    def get_warnings(self) -> list[ComplianceFinding]:
        return [f for f in self.findings if f.severity == "warn"]

    def to_checkpoint_findings(self) -> list[dict[str, Any]]:
        return [f.model_dump() for f in self.findings]
