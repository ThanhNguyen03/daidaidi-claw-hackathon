"""
Validation Validator
====================
Provides validation pre-pass using Gemma 4 fast model.
Implements C.5 §1: validation gate with severity classification.
"""

import json
from typing import Optional


from schemas.state import Brief, SalespersonProfile, ValidationReport, Ambiguity
from llm.greennode import get_llm_client, GreenNodeClient

# =============================================================================
# Validation Service
# =============================================================================


class ValidationService:
    """
    Validation service using Gemma 4 fast model.
    C.5 §1: Validates brief and emits ValidationReport.
    """

    # Mandatory fields by mode — only truly blocking fields (agents can work without budget)
    MANDATORY_FIELDS_BY_MODE = {
        "planning": ["goal"],
        "execute": ["goal"],
        "chat": [],
        "brainstorm": [],
    }

    # Fields that trigger re-validation when changed (critical edits)
    CRITICAL_FIELDS = ["industry", "target_audience"]

    # Fields with non-critical edits (no re-validation needed)
    NON_CRITICAL_FIELDS = ["budget_vnd", "timeline"]

    def __init__(self):
        self.model_key = "validation"
        self._client: Optional[GreenNodeClient] = None

    @property
    def client(self) -> GreenNodeClient:
        """Get or create LLM client for validation."""
        if self._client is None:
            try:
                self._client = get_llm_client(self.model_key)
            except ValueError:
                # Fallback to orchestrator if validation model not configured
                self._client = get_llm_client("orchestrator")
        return self._client

    def _get_mandatory_fields(self, mode: str) -> list[str]:
        """Get mandatory fields for the current mode."""
        return self.MANDATORY_FIELDS_BY_MODE.get(mode, [])

    def _check_trigger_conditions(
        self,
        brief: Brief,
        profile: Optional[SalespersonProfile],
        validation_report: ValidationReport,
    ) -> ValidationReport:
        """
        C.5 §1: Check trigger conditions for validation.

        Triggers:
        - Missing mandatory field
        - ≥2 plausible interpretations (ambiguity)
        - KB confidence < 0.7
        - Out-of-scope
        - First interaction with new salesperson
        - Post-correction recovery
        """
        # Check first interaction (no profile or empty history)
        is_first_interaction = profile is None or len(profile.history) == 0

        if is_first_interaction:
            # First interaction always needs some basic info
            if not brief.industry:
                validation_report.missing_required.append("industry")
            if not brief.goal:
                validation_report.missing_required.append("goal")

        # Check for low KB confidence (if we had KB, we'd check it)
        # For now, assume high confidence unless there's ambiguity
        if validation_report.ambiguities:
            validation_report.kb_confidence = 0.6  # Lower due to ambiguity
        else:
            validation_report.kb_confidence = 0.9

        # Determine status — only BLOCK on truly missing critical fields.
        # Ambiguities are handled by agents themselves; don't stop dispatch over them.
        if validation_report.missing_required:
            validation_report.status = "PENDING"  # Ask user, but agents will still run
            validation_report.severity = "major"
        elif validation_report.out_of_scope:
            validation_report.status = "BLOCKED"
            validation_report.severity = "critical"
        else:
            validation_report.status = "READY"
            validation_report.severity = "minor"

        return validation_report

    def _classify_severity(
        self, field_name: str, old_value: any, new_value: any
    ) -> str:
        """
        C.5 §6: Severity classifier for re-validation.
        Returns 'critical', 'major', or 'minor' based on field impact.
        """
        if field_name in self.CRITICAL_FIELDS:
            # Industry or target_audience change requires re-validation
            if old_value != new_value:
                return "critical"
        elif field_name in self.NON_CRITICAL_FIELDS:
            # Budget or timeline changes don't need re-validation
            return "minor"

        return "minor"

    async def validate(
        self,
        brief: Brief,
        profile: Optional[SalespersonProfile] = None,
        mode: str = "chat",
    ) -> ValidationReport:
        """
        Main validation function.
        Uses LLM to detect ambiguities and determine validation status.
        """
        # Start with basic mandatory field check
        mandatory_fields = self._get_mandatory_fields(mode)
        missing = []

        for field in mandatory_fields:
            value = getattr(brief, field, None)
            if not value:
                missing.append(field)

        # Create initial report
        validation_report = ValidationReport(
            missing_required=missing,
            ambiguities=[],
            kb_confidence=1.0,
            out_of_scope=False,
            status="READY",  # Will be updated below
            severity="minor",
        )

        # If we have enough info, use LLM for deeper analysis
        if brief.industry or brief.goal:
            try:
                llm_ambiguities = await self._detect_ambiguities(brief)
                validation_report.ambiguities = llm_ambiguities
            except Exception:
                # If LLM fails, fall back to basic validation
                pass

        # Check trigger conditions
        validation_report = self._check_trigger_conditions(
            brief, profile, validation_report
        )

        return validation_report

    async def _detect_ambiguities(self, brief: Brief) -> list[Ambiguity]:
        """
        Use LLM to detect ambiguities in the brief.
        C.5 §1: Detects when ≥2 plausible interpretations exist.
        """
        prompt = f"""Analyze this brief for ambiguities (multiple plausible interpretations).
Respond in JSON format:
{{
  "ambiguities": [
    {{"field": "field_name", "interpretations": ["interpretation1", "interpretation2"], "why": "why ambiguous"}}
  ]
}}

Brief:
- Industry: {brief.industry or 'not specified'}
- Budget: {brief.budget_vnd or 'not specified'}
- Goal: {brief.goal or 'not specified'}
- Timeline: {brief.timeline or 'not specified'}
- Target Audience: {brief.target_audience or 'not specified'}

If no ambiguities, respond with {{"ambiguities": []}}"""

        try:
            response = self.client.create_completion(
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                temperature=0.3,
                max_tokens=500,
            )

            content = response.choices[0].message.content if response.choices else "{}"

            # Parse JSON from response
            # Handle potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content.strip())

            ambiguities = []
            for amb in result.get("ambiguities", []):
                if amb.get("interpretations") and len(amb["interpretations"]) >= 2:
                    ambiguities.append(
                        Ambiguity(
                            field=amb.get("field", ""),
                            interpretations=amb.get("interpretations", []),
                            why=amb.get("why", ""),
                        )
                    )

            return ambiguities

        except Exception:
            # Return empty list on any error
            return []

    async def validate_with_severity(
        self,
        brief: Brief,
        profile: Optional[SalespersonProfile],
        mode: str,
        old_brief: Optional[Brief] = None,
    ) -> tuple[ValidationReport, bool]:
        """
        C.5 §6: Severity-gated re-validation.

        Returns (validation_report, should_revalidate)

        - Non-critical edit (budget change) → no re-validation
        - Critical edit (industry switch) → re-validate
        """
        # If no old brief, always validate
        if old_brief is None:
            report = await self.validate(brief, profile, mode)
            return report, True

        # Check if any critical fields changed
        should_revalidate = False
        for field in self.CRITICAL_FIELDS:
            old_value = getattr(old_brief, field, None)
            new_value = getattr(brief, field, None)
            if old_value != new_value:
                severity = self._classify_severity(field, old_value, new_value)
                if severity == "critical":
                    should_revalidate = True
                    break

        if should_revalidate:
            report = await self.validate(brief, profile, mode)
            return report, True
        else:
            # No re-validation needed, return existing status
            report = ValidationReport(
                missing_required=[],
                ambiguities=[],
                kb_confidence=1.0,
                out_of_scope=False,
                status="READY",
                severity="minor",
            )
            return report, False


# =============================================================================
# Module-level Functions
# =============================================================================

# Singleton instance
_validation_service: Optional[ValidationService] = None


def get_validation_service() -> ValidationService:
    """Get the validation service singleton."""
    global _validation_service
    if _validation_service is None:
        _validation_service = ValidationService()
    return _validation_service


async def validate(
    brief: Brief, profile: Optional[SalespersonProfile] = None, mode: str = "chat"
) -> ValidationReport:
    """
    Convenience function for validation.
    C.5 §1: Main entry point for validation.
    """
    service = get_validation_service()
    return await service.validate(brief, profile, mode)


async def validate_with_severity(
    brief: Brief,
    profile: Optional[SalespersonProfile],
    mode: str,
    old_brief: Optional[Brief] = None,
) -> tuple[ValidationReport, bool]:
    """
    Convenience function for severity-gated validation.
    C.5 §6: Used when editing an existing brief.
    """
    service = get_validation_service()
    return await service.validate_with_severity(brief, profile, mode, old_brief)
