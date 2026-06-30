from __future__ import annotations

from scbounty.config.models import Finding, TargetConfig


class ReportNotShareableError(RuntimeError):
    """Raised when a disclosure-ready report lacks required human evidence."""


def render_immunefi(target: TargetConfig, findings: list[Finding]) -> str:
    eligible = [finding for finding in findings if finding.shareable]
    if not eligible:
        raise ReportNotShareableError(
            "No finding is confirmed, in scope, and locally reproduced. "
            "Immunefi draft generation is refused."
        )
    sections = [
        "# Responsible disclosure draft",
        "",
        f"Program: {target.authorization.program_url}",
        f"Scope: {target.authorization.scope_url}",
        "",
        "This draft contains local-only reproduction steps and must be reviewed before submission.",
    ]
    if target.authorization.type == "educational_fixture":
        sections.extend(
            [
                "",
                "> EDUCATIONAL FIXTURE ONLY / DO NOT SUBMIT.",
                "> This draft proves the reporting workflow and is not a real bounty finding.",
            ]
        )
    for finding in eligible:
        sections.extend(
            [
                "",
                f"## {finding.title}",
                "",
                f"Finding ID: `{finding.finding_id}`",
                f"Severity: `{finding.severity}`",
                f"Impact category: `{finding.impact_category}`",
                "",
                "### Root cause",
                "",
                finding.description,
                "",
                "### Impact",
                "",
                finding.impact,
                "",
                "### Safe local reproduction",
                "",
                *[f"{index}. {step}" for index, step in enumerate(finding.reproduction_steps, 1)],
                "",
                "### False-positive analysis",
                "",
                *[f"- {risk}" for risk in finding.false_positive_risks],
                "",
                "### Recommended remediation",
                "",
                finding.recommended_fix,
            ]
        )
    return "\n".join(sections).strip() + "\n"
