# Reporting guide

## Triage before prose

For every candidate, record:

- exact asset URL/path and deployed address when relevant;
- current scope and impact mapping;
- attacker privileges and preconditions;
- expected versus actual behavior;
- local-only reproduction;
- evidence artifacts and hashes;
- false-positive and feasibility analysis;
- remediation.

Do not inherit a severity from Slither, Semgrep, or another tool. Automated findings are capped at
low severity until confirmed.

## Report states

- `needs_review`: automated or early manual lead.
- `rejected`: duplicate, out of scope, non-impactful, known, or false positive.
- `confirmed`: current in-scope mapping and local reproduction are recorded.

Markdown and JSON reports may contain unconfirmed findings and are prominently marked as drafts.
The Immunefi-style format refuses to render unless at least one finding is confirmed, in scope,
and locally reproduced.

## Disclosure

Remove credentials, endpoint tokens, personal data, unrelated source, and production exploit
instructions. Submit only through the current program channel. Do not automate submission.

