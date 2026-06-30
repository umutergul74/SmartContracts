# SKILL.md — Arbitrum Smart Contract Bounty Research Engineering Standards

## Purpose

This skill defines the operating rules for building and maintaining the `SmartContracts` repository: a professional, modular smart-contract security research platform for authorized bug bounty work.

The initial pilot target is **Arbitrum / ARB**. The system must help researchers find and validate potential vulnerabilities only in explicitly authorized smart-contract targets. It must never become an exploit bot, theft tool, live attack system, or uncontrolled scanner.

---

## Core principles

1. Authorization first.
2. Safety by default.
3. Local-only PoCs.
4. Reproducibility over cleverness.
5. Low false positives over noisy results.
6. Evidence-backed findings only.
7. Human triage before conclusions.
8. Responsible disclosure always.
9. Modular architecture suitable for team development.
10. Clear logs, typed schemas, deterministic artifacts.
11. No secrets in code, logs, commits, examples, or reports.
12. Never claim a bounty-worthy finding without scope mapping and impact evidence.

---

## Absolute prohibitions

Do not implement, generate, or suggest:

- live mainnet exploit execution,
- public testnet exploit execution where the program prohibits it,
- fund-draining transaction scripts,
- wallet private-key handling for exploit execution,
- automated bounty submission,
- front-running, back-running, sandwiching, or MEV exploitation,
- bypassing authentication, rate limits, or program scope,
- public disclosure of unpatched bugs,
- scanning targets without explicit authorization,
- scanning off-chain infrastructure unless explicitly in scope,
- destructive testing against production systems,
- automated traffic generation that could degrade third-party systems,
- scripts that broadcast transactions to Ethereum, Arbitrum One, Arbitrum Nova, or any public network.

PoCs must be limited to local tests, local forks, private ephemeral devnets, or isolated simulations.

---

## Arbitrum pilot rules

The Arbitrum target must be treated as a high-value, high-risk, production L2 infrastructure target.

### Scope source

Use the Arbitrum Immunefi bug bounty program as the primary authorization and scope source:

- Program: `https://immunefi.com/bug-bounty/arbitrum/`
- Scope: `https://immunefi.com/bug-bounty/arbitrum/scope/`
- Information: `https://immunefi.com/bug-bounty/arbitrum/information/`

The repository may contain a seed snapshot, but the tool must require re-verification before meaningful analysis or report generation.

### Seed focus

Prioritize:

- ARB token contracts,
- DAO/governance and upgrade-related contracts,
- canonical token bridge contracts,
- L1/L2 gateway contracts,
- Arbitrum Nitro contracts where in scope,
- deployed contracts used by Arbitrum One and Arbitrum Nova where the live program scope allows.

Do not assume every Arbitrum-related repository, tutorial, SDK, website, RPC service, sequencer component, or off-chain component is in scope.

### Seed in-scope asset names

The initial config may include these seed assets from the public scope snapshot, but must not treat the list as complete or permanently current:

- `IArbToken.sol`
- `L2ArbitrumMessenger.sol`
- `StandardArbERC20.sol`
- `L2ArbitrumGateway.sol`
- `L2CustomGateway.sol`
- `L2ERC20Gateway.sol`
- `L2GatewayRouter.sol`
- `L2WethGateway.sol`
- `ICustomToken.sol`
- `L1ArbitrumMessenger.sol`
- `L1ArbitrumExtendedGateway.sol`
- `L1ArbitrumGateway.sol`

### Seed repositories

Use these repositories as source references when in scope:

- `https://github.com/OffchainLabs/token-bridge-contracts`
- `https://github.com/OffchainLabs/nitro-contracts`

Do not assume repository source equals deployed bytecode. Fetch metadata and compare when possible.

---

## Required project behavior

Every target must pass a scope gate before analysis unless it is an educational local fixture.

A target is authorized only when the target config contains enough evidence for:

- authorization type,
- program or disclosure URL,
- exact in-scope assets/contracts or an approved source of truth,
- allowed testing methods,
- prohibited testing methods,
- disclosure contact or submission process,
- last verification timestamp,
- local-only PoC policy.

If authorization is unclear, the CLI must refuse to run and explain what metadata is missing.

For Arbitrum, the scope gate must explicitly print that live network transaction testing is prohibited and that PoCs are local-only.

---

## Preferred workflow

Use this pipeline:

1. Target discovery.
2. Scope validation.
3. Source acquisition.
4. Deployed metadata acquisition where allowed.
5. Build reproduction.
6. Static analysis.
7. Custom heuristic analysis.
8. Arbitrum-specific threat modeling.
9. Harness generation.
10. Fuzz/invariant testing.
11. Symbolic testing where appropriate.
12. Manual triage.
13. Safe local PoC.
14. Report generation.
15. Responsible disclosure.

Do not skip scope validation.

---

## Arbitrum-specific threat areas

Prioritize vulnerabilities with plausible impact in these areas.

### Bridge and gateway security

Look for:

- incorrect L1/L2 token mapping,
- router/gateway bypass,
- unauthorized `bridgeMint` or `bridgeBurn`,
- incorrect gateway registration assumptions,
- cross-domain sender validation mistakes,
- address aliasing mistakes,
- retryable ticket lifecycle errors,
- unsafe refund receiver handling,
- withdrawal finalization edge cases,
- message replay or duplicate finalization,
- malformed message encoding/decoding,
- WETH wrapping/unwrapping mismatch,
- escrow/mint/burn accounting mismatch,
- stuck-funds conditions,
- insolvency paths.

### Governance and upgradeability

Look for:

- uninitialized implementation contracts,
- unsafe initializer/reinitializer patterns,
- storage layout mismatch indicators,
- unsafe proxy admin assumptions,
- timelock or upgrade executor path mistakes,
- governance execution replay assumptions,
- role drift between L1 and L2,
- emergency vs non-emergency execution confusion,
- unexpected privileged function reachability.

### Gas griefing and DoS

Look for:

- unbounded loops over user-controlled data,
- gas-heavy finalization paths,
- retryable parameter griefing,
- contracts unable to operate due to lack of funds,
- gas theft,
- unbounded gas consumption,
- DoS that maps to the bounty’s impact categories.

Avoid low-impact gas micro-optimizations without a concrete security impact.

---

## Repository quality standards

All code must be:

- typed where practical,
- organized by domain responsibility,
- testable,
- deterministic,
- documented enough for another engineer to continue,
- conservative in claims,
- safe by default.

Use:

- Python package structure under `src/scbounty/`,
- `pydantic` config and finding models,
- `typer` CLI,
- `rich` output,
- `pytest` tests,
- `ruff` linting/formatting,
- GitHub Actions CI,
- `.env.example` without secrets,
- `.gitignore` that excludes `.env`, keys, generated artifacts, caches, and large local repos.

---

## Analyzer adapter standards

Each analyzer integration must:

- check availability before running,
- capture version,
- capture command line,
- capture start/end time,
- capture stdout/stderr safely,
- return structured results,
- avoid crashing the whole pipeline if missing,
- avoid requiring secrets,
- avoid broadcasting transactions.

Supported adapter stubs:

- Foundry,
- Slither,
- Aderyn,
- Mythril,
- Echidna,
- Medusa,
- Halmos,
- Semgrep,
- Solhint.

---

## Findings standards

A finding must include:

- title,
- severity,
- confidence,
- category,
- affected contracts/functions,
- source locations,
- impact,
- exploitability notes,
- safe PoC status,
- evidence,
- false-positive risks,
- recommended fix,
- scope status,
- references.

Never mark a finding as `high` or `critical` only because a tool said so. Severity must be based on actual impact and scope rules.

For Arbitrum, prioritize impacts such as:

- direct theft of funds,
- permanent freezing of funds,
- insolvency,
- serious withdrawal/bridge damage,
- network-wide DoS where in scope,
- gas theft or unbounded gas consumption where in scope.

---

## Harness and PoC standards

Harnesses must be safe.

Allowed:

- toy local vulnerable fixtures,
- Foundry local unit tests,
- Foundry local fork simulations with read-only RPC,
- Echidna local fuzzing,
- Medusa local fuzzing,
- Halmos symbolic tests,
- simulated exploit paths against fixtures.

Not allowed:

- transaction broadcasting,
- real private keys,
- live exploitation,
- public testnet exploitation when prohibited,
- scripts designed to steal, drain, lock, grief, or disrupt real users.

PoC language must be framed as local reproduction, not attack instructions for production.

---

## Local environment standards

The project must support local work with Codex.

Document setup for:

- Python 3.11+ / 3.12+,
- `uv` preferred and `pip` fallback,
- Foundry,
- Node.js LTS,
- optional Docker,
- optional analyzers.

The repo must work in degraded mode:

- If no RPC URLs exist, run static/source-only checks.
- If optional analyzers are missing, warn and continue.
- If scope cannot be verified, refuse real target analysis but allow toy fixtures.

Never require private keys.

---

## Documentation standards

The repository must contain:

- `README.md` — product-quality overview.
- `SECURITY.md` — responsible disclosure and safety policy.
- `docs/ETHICS_AND_SCOPE.md` — legal/ethical boundaries.
- `docs/LOCAL_SETUP.md` — local setup instructions.
- `docs/ARBITRUM_PILOT.md` — Arbitrum target notes.
- `docs/THREAT_MODEL_ARBITRUM.md` — Arbitrum threat model.
- `docs/ARCHITECTURE.md` — module architecture.
- `docs/REPORTING_GUIDE.md` — report writing guidance.
- `docs/TOOLING_MATRIX.md` — analyzer tool matrix.

Docs must clearly state that this is not a live exploit framework.

---

## Git and GitHub standards

Work against:

`https://github.com/umutergul74/SmartContracts.git`

Use professional commit messages.
Do not commit secrets.
Do not commit `.env`.
Do not commit private keys.
Do not commit huge generated artifacts unless intentionally documented.

Initial commit message:

`Initialize Arbitrum smart contract bounty research platform`

If pushing fails due to authentication, leave the working tree clean and print the manual commands.

---

## Final response standards for Codex

After completing a task, report:

- what changed,
- commands run,
- tests passed/failed,
- tools detected/missing,
- whether the repo was pushed,
- next recommended step.

Do not overclaim. Say clearly when something is a scaffold, stub, or placeholder.
