# Requirement Elicitation Agent (A1) - Skill Map

## 1. Agent Role
Customer discovery expert. Normalizes incomplete briefs into a structured requirement summary and maps constraint signals for downstream agents.

## 2. Core Skills
- Customer current state discovery (AS-IS)
- Business objective & target audience elicitation
- Engagement mechanics & reward budget discovery
- Existing system & integration requirements extraction
- Non-technical translation and jargon reduction

## 3. Workflow & Step-by-Step Logic
Review current brief -> infer requirement structure from explicit context -> identify gaps without blocking the flow -> hand off to downstream agents with unconfirmed items marked clearly.

## 4. Reference Skills List
Below are the detailed skill files in the `reference/` directory that this agent refers to:

| Filename | Purpose / Scope |
|---|---|
| [requirement-elicitor.md](reference/requirement-elicitor.md) | Reference guidelines for this skill module. |

## 5. Expected Outputs & Formats
- Requirement Summary (AS-IS, TO-BE, Constraints)
- Constraint Map (In-scope, config, integration, custom, out-of-scope)
- Missing / unconfirmed items list for downstream agents
