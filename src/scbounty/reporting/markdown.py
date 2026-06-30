from __future__ import annotations

from jinja2 import Environment, StrictUndefined

from scbounty.config.models import Finding, TargetConfig

_TEMPLATE = """\
# {{ target.name }} research report

> **DRAFT / NOT A VALIDATED BOUNTY FINDING**
>
> This report is generated for authorized, local-only research. Tool output requires human
> triage, current scope mapping, and safe reproduction before disclosure.

- Program: {{ target.authorization.program_url }}
- Scope: {{ target.authorization.scope_url }}
- Findings: {{ findings | length }}

{% for finding in findings %}
## {{ finding.finding_id }} - {{ finding.title }}

- Severity: `{{ finding.severity }}`
- Confidence: `{{ finding.confidence }}`
- Scope: `{{ finding.scope_status }}`
- Triage: `{{ finding.triage_status }}`
- Detector: `{{ finding.detector }}`

{{ finding.description }}

### Impact

{{ finding.impact }}

### Evidence

{% for item in finding.evidence %}
- {{ item.summary }}
{% endfor %}

### False-positive risks

{% for risk in finding.false_positive_risks %}
- {{ risk }}
{% endfor %}

### Recommended remediation

{{ finding.recommended_fix }}

{% endfor %}
"""


def render_markdown(target: TargetConfig, findings: list[Finding]) -> str:
    environment = Environment(undefined=StrictUndefined, autoescape=False)
    return (
        environment.from_string(_TEMPLATE).render(target=target, findings=findings).strip() + "\n"
    )
