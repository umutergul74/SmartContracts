# Ethics, authorization, and scope

Authorization is a runtime requirement, not a checkbox in documentation. A real target is eligible
only when its configuration identifies the program, live scope source, allowed and prohibited
methods, disclosure channel, verification date, and local-only PoC policy.

## Fail-closed rules

`scbounty` refuses real-target analysis when:

- the live scope page is unavailable;
- the page cannot be parsed deterministically;
- asset or impact fingerprints differ from the reviewed snapshot;
- required safety language is missing;
- configuration contains unknown fields or omits required prohibitions.

Educational fixtures use a separate authorization type and cannot be mistaken for production
targets.

## Research boundaries

Reading public source, compiling a pinned checkout, static analysis, local fuzzing, symbolic
testing, and read-only fork simulation may be appropriate when the program allows them. Source
repository membership alone does not make every file in scope.

Do not test production deployments. Do not use third-party oracles, frontends, APIs, sequencers,
RPC infrastructure, or unrelated contracts unless the live program explicitly authorizes them.

## Evidence standard

Tool output is a lead. A disclosure candidate needs:

1. exact current scope mapping;
2. concrete program impact;
3. locally reproduced behavior or comparably strong evidence;
4. explicit false-positive analysis;
5. human confirmation.

