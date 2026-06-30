# Tooling matrix

| Tool | First-slice status | Purpose | Failure behavior |
|---|---|---|---|
| Foundry | Active | Build, local fixture, fuzz, invariant | Structured failure/skip |
| Slither | Active | Solidity AST/IR and baseline detectors | Structured failure/skip |
| Semgrep CE | Active | Committed local source rules | Structured failure/skip |
| Aderyn | Adapter | Additional static analysis | Availability-only skip |
| Mythril | Adapter | Selected symbolic execution | Availability-only skip |
| Echidna | Adapter + template | Stateful fuzzing | Availability-only skip |
| Medusa | Adapter + template | Parallel fuzzing | Availability-only skip |
| Halmos | Adapter | Foundry-compatible symbolic tests | Availability-only skip |
| Solhint | Adapter | Solidity lint signal | Availability-only skip |

Every adapter records availability, version, command, timing, exit status, and sanitized output.
Missing optional tools never masquerade as successful scans.

