# scbounty

`scbounty` is a local-first smart-contract security research workbench for explicitly authorized
bug-bounty and responsible-disclosure targets. Arbitrum is the first pilot.

This repository is not an exploit bot, transaction broadcaster, wallet tool, or unattended
scanner. It cannot submit bounties and does not treat analyzer output as a validated
vulnerability.

## What works in the first vertical slice

- Fail-closed live comparison of the Arbitrum Immunefi scope against a reviewed snapshot.
- Commit-pinned source acquisition for reviewed Offchain Labs repositories.
- Block-pinned, read-only bytecode, EIP-1967, and reviewed fixed-call manifests.
- Foundry, Slither, and Semgrep adapters with versioned, structured execution records.
- Degraded mode when optional analyzers or read-only RPC URLs are absent.
- Conservative bridge, gateway, cross-chain sender, accounting, upgrade, and gas detectors.
- A deliberately vulnerable local toy bridge with safe Foundry reproductions.
- Human triage records and Markdown, JSON, and gated Immunefi-style report generation.

## Safety model

Every real target must pass the scope gate in the same analysis run. Any network failure, parser
failure, asset-list change, impact change, or missing safety marker stops analysis. Public network
transactions and private-key handling are not implemented.

Generated data lives under ignored `artifacts/` and `.scbounty/cache/` directories. Do not commit
unpublished findings.

## Quick start

Python 3.12 is the canonical environment. The package supports Python 3.11–3.13.

### Windows PowerShell

```powershell
uv python install 3.12
uv venv --python 3.12
.venv\Scripts\Activate.ps1
uv sync --extra dev

scbounty env doctor
scbounty targets show arbitrum
scbounty scope check arbitrum
scbounty scope coverage arbitrum
scbounty scope coverage arbitrum --format json --output artifacts/scope/arbitrum/coverage.json
scbounty scope coverage arbitrum --format markdown --output artifacts/scope/arbitrum/coverage.md
scbounty source fetch arbitrum
scbounty source metadata arbitrum
scbounty analyze arbitrum --safe
```

### Linux or macOS

```bash
uv python install 3.12
uv venv --python 3.12
source .venv/bin/activate
uv sync --extra dev

scbounty env doctor
scbounty scope check arbitrum
scbounty scope coverage arbitrum
scbounty source metadata arbitrum
scbounty analyze arbitrum --safe
```

`pip install -e '.[dev]'` is supported when `uv` is unavailable.

## CLI

```text
scbounty targets list
scbounty targets show arbitrum
scbounty scope check arbitrum
scbounty scope coverage arbitrum
scbounty scope coverage arbitrum --format json --output artifacts/scope/arbitrum/coverage.json
scbounty scope coverage arbitrum --format markdown --output artifacts/scope/arbitrum/coverage.md
scbounty source fetch arbitrum
scbounty source metadata arbitrum
scbounty analyze arbitrum --safe
scbounty analyze arbitrum --tool slither
scbounty harness generate arbitrum --kind foundry
scbounty test arbitrum --kind invariant --local-only
scbounty findings list arbitrum --run-id <run>
scbounty findings triage <finding> --run-id <run> --status <status> --note-file <path>
scbounty report generate arbitrum --format markdown
scbounty report generate arbitrum --format json
scbounty report generate arbitrum --format immunefi
scbounty env doctor
```

The Immunefi format is refused unless a finding is manually confirmed, mapped to current scope,
and reproduced on a local fixture or local fork.

## Repository map

- `src/scbounty/config`: typed target metadata and the fail-closed scope gate.
- `src/scbounty/source`: pinned source and read-only deployed metadata.
- `src/scbounty/analyzers`: external-tool adapters and orchestration.
- `src/scbounty/detectors`: conservative Arbitrum-aware source signals.
- `src/scbounty/harness`: local harness generation.
- `src/scbounty/reporting`: triage and draft reports.
- `targets/arbitrum`: reviewed authorization snapshot and bridge/governance/fund profile.
- `tests/fixtures/toy_bridge`: educational vulnerable and safe controls.
- `tests/fixtures/retryable_alias_recovery`: local EIP-7702/refund-alias recovery model.

See [architecture](docs/ARCHITECTURE.md), [local setup](docs/LOCAL_SETUP.md), and the
[Arbitrum threat model](docs/THREAT_MODEL_ARBITRUM.md).

## Contributing

Keep changes typed, deterministic, locally testable, and conservative in their claims. New
detectors require positive and negative fixtures. New external commands must use the shared safe
runner and must not introduce wallet, deployment, or transaction-broadcast capability.

Licensed under Apache-2.0.
