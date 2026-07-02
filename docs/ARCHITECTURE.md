# Architecture

## Trust boundaries

Target configuration and reviewed snapshots are trusted repository inputs. Live web pages,
downloaded source, RPC responses, analyzer output, and generated reports are untrusted data.

## Pipeline

1. Pydantic rejects incomplete or unsafe target configuration.
2. The scope gate makes one live request and compares complete normalized fingerprints.
3. The source layer shallow-clones reviewed repositories and records immutable commit IDs.
4. The optional deployed-metadata layer pins one block per configured network and records
   bytecode, EIP-1967 implementation/admin/beacon fingerprints, and explicitly configured
   fixed-calldata calls using read-only RPC.
5. Build/analyzer adapters execute fixed argument lists through a secrets-stripping runner.
6. Detectors emit low-severity, possibly-in-scope research signals.
7. Deduplication combines evidence from equivalent signals.
8. Human triage records scope and local reproduction decisions.
9. Report gates prevent unconfirmed disclosure drafts.

## Artifacts

Each analysis run receives `artifacts/runs/<run-id>/` containing:

- `run.json`
- `scope-attestation.json`
- `source-manifest.json`
- `findings.json`
- optional `triage/` records
- optional `reports/`

Source checkouts live under `.scbounty/cache/sources/`. Both trees are ignored by Git.
Standalone deployed snapshots live under `artifacts/deployed/<target-id>/`. They contain the RPC
environment-variable name but never the endpoint URL or token. Fixed calls are target-configured,
block-pinned, decoded into a declared scalar type, and preserved as review evidence. An unexpected
value produces a warning rather than an automatic vulnerability claim.

## Extension points

Analyzers implement `AnalyzerAdapter`. Detectors implement a source-to-findings protocol. New
targets add typed YAML and a reviewed scope snapshot. All extension points return normalized
models and must fail without taking down unrelated pipeline stages.
