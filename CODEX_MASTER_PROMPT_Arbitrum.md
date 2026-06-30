# CODEX MASTER PROMPT — Arbitrum-Focused Smart Contract Bug Bounty Research Platform

You are Codex acting as a senior smart-contract security engineer, security tooling architect, DevSecOps engineer, and production-grade open-source maintainer.

Build the initial repository for a professional, modular smart-contract bug-bounty research platform in this GitHub repository:

`https://github.com/umutergul74/SmartContracts.git`

This must not look like a small hobby script. It must look like the beginning of a serious team/product codebase: clean architecture, reproducible local environment, CI, deterministic outputs, professional documentation, modular analyzers, safety controls, and evidence-backed reporting.

The first pilot target is **Arbitrum / ARB**, with focus on authorized smart-contract bug bounty research only.

---

## 0. Mission

Build a platform that helps a researcher legally and responsibly identify potential smart-contract vulnerabilities in explicitly authorized bug bounty or responsible disclosure targets.

The short-term strategy is:

1. Start with **Arbitrum as the pilot target**.
2. Do not try to scan the entire top 200/300 crypto universe in the first version.
3. Build a robust audit pipeline around Arbitrum’s in-scope smart contracts and related deployed contracts.
4. After the pipeline proves useful, generalize it to other scoped protocols.

The long-term product vision is a modular research workbench that can:

- discover and rank candidate bug bounty targets,
- verify that a target is authorized and in scope,
- fetch verified source code and metadata,
- reproduce builds when possible,
- run static analyzers,
- run custom heuristics and detectors,
- generate threat models,
- generate Foundry/Echidna/Medusa fuzz and invariant harnesses,
- run safe local fork simulations,
- triage false positives,
- produce professional bug-bounty reports.

---

## 1. Non-negotiable safety and legal boundaries

This project is for authorized security research only.

Implement and document these rules directly in the repository:

- Analyze only targets with explicit authorization: bug bounty program, audit contest, public responsible disclosure policy, or written permission.
- For Arbitrum, treat the Immunefi Arbitrum program as the primary authorization source, but **always re-check the live scope before running analysis**.
- Do not deploy, broadcast, or submit exploit transactions against Ethereum mainnet, Arbitrum One, Arbitrum Nova, Arbitrum Sepolia, or any other live/public network.
- Do not perform live exploit attempts on mainnet or public testnet deployed contracts.
- All PoCs must run only in local tests, local forks, isolated simulations, or private ephemeral development chains.
- RPC usage must be read-only by default.
- Never include private keys, real wallets, fund-moving scripts, drain logic, MEV logic, exploit automation, front-running, back-running, or sandwiching.
- Never bypass rate limits, authentication, paywalls, or access controls.
- Never scan infrastructure, APIs, web apps, bridges, frontends, sequencers, RPC endpoints, or off-chain services unless a program explicitly includes them.
- Never generate significant automated traffic against third-party services.
- Never publicly disclose unpatched vulnerabilities.
- Any report must follow responsible disclosure rules and the target program’s scope.

Add `SECURITY.md` and `docs/ETHICS_AND_SCOPE.md` explaining these boundaries clearly.

The CLI must refuse to run against any target unless a scope gate passes.

---

## 2. Pilot target: Arbitrum / ARB

### 2.1 Target interpretation

The user says “Arbitrum coin,” but the research target must not be limited to price, trading, or the ERC-20 token only.

Interpret the pilot as:

- Arbitrum / ARB ecosystem smart-contract bug bounty research.
- Primary scope source: Arbitrum’s Immunefi bug bounty program.
- Primary technical areas:
  - ARB token and DAO/governance contracts,
  - canonical token bridge contracts,
  - L1/L2 gateway contracts,
  - Arbitrum Nitro protocol contracts where in scope,
  - deployed contracts used by Arbitrum One and Arbitrum Nova where the bounty scope allows.

Do **not** assume every Arbitrum-related contract is in scope. Scope must be explicit.

### 2.2 Required Arbitrum target config

Create a committed seed config at:

`targets/arbitrum/arbitrum.yaml`

The config must include at least:

```yaml
target_id: arbitrum
name: Arbitrum / ARB
status: pilot
risk_profile: critical_infrastructure_l2

authorization:
  type: bug_bounty
  platform: Immunefi
  program_name: Arbitrum
  program_url: https://immunefi.com/bug-bounty/arbitrum/
  scope_url: https://immunefi.com/bug-bounty/arbitrum/scope/
  information_url: https://immunefi.com/bug-bounty/arbitrum/information/
  last_manually_verified_utc: "2026-06-30"
  must_reverify_before_run: true
  poc_required: true
  kyc_required_for_payout: true

allowed_testing:
  - static_analysis
  - source_review
  - local_unit_tests
  - local_fork_read_only_simulation
  - invariant_testing_against_local_fork
  - fuzzing_against_local_fixtures
  - symbolic_testing_against_local_fixtures

prohibited_testing:
  - mainnet_transactions
  - public_testnet_transactions
  - live_exploit_attempts
  - destructive_dos
  - significant_traffic_generation
  - third_party_oracle_testing_without_scope
  - offchain_infrastructure_testing_without_scope
  - automated_bounty_submission

networks:
  ethereum_l1:
    chain_id: 1
    role: parent_chain
    rpc_env_var: ETHEREUM_RPC_URL
  arbitrum_one:
    chain_id: 42161
    role: primary_l2
    rpc_env_var: ARBITRUM_ONE_RPC_URL
  arbitrum_nova:
    chain_id: 42170
    role: anytrust_l2
    rpc_env_var: ARBITRUM_NOVA_RPC_URL
  arbitrum_sepolia:
    chain_id: 421614
    role: testnet_reference_only
    rpc_env_var: ARBITRUM_SEPOLIA_RPC_URL

source_repositories:
  - name: OffchainLabs/token-bridge-contracts
    url: https://github.com/OffchainLabs/token-bridge-contracts
    purpose: canonical_token_bridge_contracts
  - name: OffchainLabs/nitro-contracts
    url: https://github.com/OffchainLabs/nitro-contracts
    purpose: core_arbitrum_nitro_contracts

seed_in_scope_assets_from_immunefi_first_page:
  - IArbToken.sol
  - L2ArbitrumMessenger.sol
  - StandardArbERC20.sol
  - L2ArbitrumGateway.sol
  - L2CustomGateway.sol
  - L2ERC20Gateway.sol
  - L2GatewayRouter.sol
  - L2WethGateway.sol
  - ICustomToken.sol
  - L1ArbitrumMessenger.sol
  - L1ArbitrumExtendedGateway.sol
  - L1ArbitrumGateway.sol

seed_dao_addresses:
  arb_token_arbitrum_one: "0x912CE59144191C1204E64559FE8253a0e49E6548"
  arb_token_ethereum_bridged: "0xB50721BCf8d664c30412Cfbc6cf7a15145234ad1"
  arb_token_nova_bridged: "0xf823C3cD3CeBE0a1fA952ba88Dc9EEf8e0Bf46AD"
  arb_gateway_arbitrum_one: "0xCaD7828a19b363A2B44717AFB1786B5196974D8E"
  arb_gateway_l1_ethereum: "0xbbcE8aA77782F13D4202a230d978F361B011dB27"
  arb_gateway_nova: "0xbf544970E6BD77b21C6492C281AB60d0770451F4"

impact_categories_to_prioritize:
  critical:
    - direct_theft_of_user_funds
    - permanent_freezing_of_funds_not_fixable_by_upgrade
    - insolvency
  high:
    - permanent_freezing_fixable_by_upgrade
    - reorg_related_bugs
    - fast_bridge_withdrawal_damage
    - network_wide_dos_not_rpc_only
  medium:
    - griefing_with_protocol_or_user_damage
    - theft_of_gas
    - unbounded_gas_consumption
    - contract_unable_to_operate_due_to_lack_of_funds
    - block_stuffing_for_profit
```

Important: this seed config is not a substitute for live scope validation. Build a scope verifier that compares this seed with the latest available public scope page and warns/refuses when stale.

---

## 3. Arbitrum-specific research focus

Prioritize issues that are realistically relevant to Arbitrum-style L1/L2 systems and token bridge contracts.

### 3.1 Canonical bridge and gateway logic

Focus on:

- token accounting mismatch between L1 escrow and L2 minted/burned balances,
- incorrect L1/L2 token mapping,
- gateway/router bypasses,
- unauthorized gateway registration or remapping,
- replay or duplicate message finalization,
- refund receiver and retryable ticket edge cases,
- message encoding/decoding inconsistencies,
- unsafe assumptions about cross-domain sender identity,
- address aliasing mistakes,
- incorrect bridgeMint / bridgeBurn access control,
- stuck funds due to malformed retryable parameters,
- withdrawal finalization assumptions,
- WETH wrapping/unwrapping accounting errors,
- custom gateway edge cases,
- upgradeability interactions with gateway routing.

### 3.2 Governance, token, and upgradeability

Focus on:

- proxy/admin ownership assumptions,
- timelock and upgrade executor interactions,
- governor execution path assumptions,
- privileged function reachability,
- role drift across L1/L2,
- incorrect emergency vs non-emergency execution assumptions,
- stale or incorrect implementation addresses,
- initialization/re-initialization risks in proxied contracts,
- storage layout risks in upgradeable contracts,
- governance action replay or cross-chain execution issues.

### 3.3 Arbitrum-specific environment assumptions

Add detectors and tests for:

- use of `block.number`, `block.timestamp`, `tx.origin`, `msg.sender`, and chain-specific assumptions,
- sequencer downtime assumptions,
- L1/L2 gas pricing assumptions,
- cross-chain finality assumptions,
- retryable ticket lifecycle assumptions,
- child-to-parent message execution assumptions,
- parent-to-child aliasing assumptions,
- Nova vs One differences where scope allows.

### 3.4 What not to chase first

Avoid spending the first phase on:

- tiny style issues,
- documentation inconsistencies,
- best-practice-only critiques without impact,
- known public issues without a new impact,
- gas micro-optimizations without security impact,
- economic/governance attacks requiring unrealistic privileged control,
- off-chain infrastructure issues,
- exchange/listing/token-price topics.

---

## 4. Local-first environment requirement

The repository must be usable locally with Codex and terminal commands.

Assume the developer is working on a local machine and wants Codex to create, edit, run, test, and commit code.

### 4.1 Local requirements

Create clear setup docs for:

- Git
- Python 3.11+ or 3.12+
- `uv` preferred, `pip` fallback
- Node.js LTS + corepack/yarn where needed
- Foundry (`forge`, `cast`, `anvil`)
- Docker / Docker Compose as optional but recommended
- Slither
- Aderyn
- Echidna
- Medusa
- Mythril
- Halmos
- Semgrep
- Solhint

Do not make every tool mandatory for the first successful run. Implement adapter discovery:

- If a tool is installed, run it.
- If missing, emit a clear warning and continue with available analyzers.
- The final report must include which tools ran, which were skipped, versions, timestamps, config hash, target hash, and command lines.

### 4.2 Local fork policy

Fork tests may require read-only RPC URLs:

- `ETHEREUM_RPC_URL`
- `ARBITRUM_ONE_RPC_URL`
- `ARBITRUM_NOVA_RPC_URL`
- `ARBITRUM_SEPOLIA_RPC_URL` only for reference/testing if permitted by scope

Never require private keys.
Never broadcast transactions.
Foundry commands must use local/anvil or fork simulation only.

Example safe pattern:

```bash
forge test --fork-url "$ARBITRUM_ONE_RPC_URL" --match-path 'test/arbitrum/**/*.t.sol'
```

Do not use commands that broadcast or send live transactions.

### 4.3 Codex workflow

After creating the initial scaffold, Codex must:

1. Initialize the repo if needed.
2. Create all files.
3. Run formatters and tests that are available.
4. Produce a clear final summary.
5. Commit changes.
6. Push to:

```bash
git remote add origin https://github.com/umutergul74/SmartContracts.git || true
git branch -M main
git add .
git commit -m "Initialize Arbitrum smart contract bounty research platform"
git push -u origin main
```

If authentication blocks the push, Codex must leave the repo clean and print the exact commands for the user to run manually.

---

## 5. Tech stack requirements

### 5.1 Core language and orchestration

Use:

- Python 3.11+ or 3.12+
- `uv` if available, `pip` fallback
- `pydantic` for typed configs and findings
- `typer` for CLI
- `rich` for readable terminal output
- `orjson` or standard `json` for structured outputs
- `pytest` for unit tests
- `ruff` for linting/formatting
- `mypy` or `pyright` if practical

### 5.2 Smart-contract testing and analysis adapters

Scaffold integration points for:

- Foundry: build, unit tests, fork tests, fuzzing, invariant tests
- Slither: static analysis and custom detector integration
- Aderyn: additional Solidity static analysis
- Mythril: symbolic execution for selected contracts
- Echidna: property-based fuzzing
- Medusa: parallelized fuzzing campaigns
- Halmos: symbolic testing for Foundry-compatible tests
- Semgrep: custom Solidity rules
- Solhint: style/security linting when useful
- `cast`: read-only on-chain metadata fetching

Create a pluggable adapter interface:

```python
class AnalyzerAdapter(Protocol):
    name: str
    def is_available(self) -> bool: ...
    def version(self) -> str | None: ...
    def run(self, target: TargetConfig, workspace: Path) -> AnalyzerResult: ...
```

---

## 6. Required repository structure

Create this structure:

```text
SmartContracts/
  README.md
  SECURITY.md
  LICENSE
  .gitignore
  .env.example
  pyproject.toml
  uv.lock                       # if generated
  Makefile
  docker-compose.yml             # optional but preferred
  Dockerfile                     # optional but preferred
  .pre-commit-config.yaml
  .github/
    workflows/
      ci.yml
      security.yml
  docs/
    ETHICS_AND_SCOPE.md
    LOCAL_SETUP.md
    ARBITRUM_PILOT.md
    ARCHITECTURE.md
    REPORTING_GUIDE.md
    TOOLING_MATRIX.md
    THREAT_MODEL_ARBITRUM.md
  targets/
    arbitrum/
      arbitrum.yaml
      README.md
      scope_snapshot.md
      notes.md
  src/
    scbounty/
      __init__.py
      cli.py
      config/
        models.py
        loader.py
        scope_gate.py
      targets/
        registry.py
        arbitrum.py
      source/
        fetcher.py
        github.py
        explorers.py
        metadata.py
      analyzers/
        base.py
        foundry.py
        slither.py
        aderyn.py
        mythril.py
        echidna.py
        medusa.py
        halmos.py
        semgrep.py
        solhint.py
      detectors/
        base.py
        arbitrum_bridge.py
        access_control.py
        upgradeability.py
        cross_chain_messaging.py
        accounting.py
        gas_griefing.py
        unsafe_erc20.py
      harness/
        foundry_generator.py
        echidna_generator.py
        medusa_generator.py
      reporting/
        models.py
        markdown.py
        json_report.py
        immunefi_template.py
      utils/
        command.py
        hashing.py
        logging.py
        paths.py
        versions.py
  semgrep/
    solidity/
      arbitrum-cross-chain.yml
      bridge-accounting.yml
      upgradeability.yml
  templates/
    reports/
      immunefi_report.md.j2
      triage_note.md.j2
    foundry/
      invariant_test.t.sol.j2
      fork_poc_test.t.sol.j2
    echidna/
      echidna.yaml.j2
  tests/
    unit/
      test_scope_gate.py
      test_config_loader.py
      test_finding_model.py
    fixtures/
      toy_bridge/
        src/
        test/
```

---

## 7. CLI requirements

Create a CLI named `scbounty`.

Required commands:

```bash
scbounty targets list
scbounty targets show arbitrum
scbounty scope check arbitrum
scbounty source fetch arbitrum
scbounty analyze arbitrum --safe
scbounty analyze arbitrum --tool slither
scbounty harness generate arbitrum --kind foundry
scbounty test arbitrum --kind invariant --local-only
scbounty report generate arbitrum --format markdown
scbounty report generate arbitrum --format json
scbounty env doctor
```

Behavior:

- `scope check` must run before `analyze`.
- `--safe` must be the default behavior.
- Any command that would require live transaction broadcasting must not exist.
- The CLI must never ask for or load private keys.
- Missing RPC URLs should not break static analysis.
- Missing external tools should result in clear warnings, not crashes.

---

## 8. Scope gate requirements

Implement `src/scbounty/config/scope_gate.py`.

The scope gate must validate:

- authorization exists,
- program URL exists,
- scope URL exists,
- target has explicit in-scope assets or an approved source of truth,
- testing methods are allowed,
- prohibited methods are documented,
- disclosure channel exists,
- last verification date exists,
- `must_reverify_before_run` is true for Arbitrum,
- no private-key or broadcast mode is configured.

For Arbitrum specifically, the CLI must print a message like:

```text
Arbitrum scope gate passed for local/static analysis only.
Live network transaction testing is prohibited.
PoCs must be local fork or isolated simulation only.
Re-check Immunefi scope before submitting any report.
```

---

## 9. Finding model

Create a normalized finding schema:

```python
class Finding(BaseModel):
    finding_id: str
    target_id: str
    title: str
    severity: Literal["info", "low", "medium", "high", "critical"]
    confidence: Literal["low", "medium", "high"]
    category: str
    detector: str
    tool: str | None
    affected_contracts: list[str]
    affected_functions: list[str]
    source_locations: list[SourceLocation]
    description: str
    impact: str
    exploitability_notes: str
    safe_poc_status: Literal["not_started", "local_fixture", "local_fork", "needs_manual_triage", "not_reproducible"]
    reproduction_steps: list[str]
    evidence: list[EvidenceItem]
    false_positive_risks: list[str]
    recommended_fix: str
    references: list[str]
    scope_status: Literal["in_scope", "possibly_in_scope", "out_of_scope", "unknown"]
    created_at_utc: datetime
```

The system must never claim a valid bounty issue without:

- in-scope asset mapping,
- plausible impact,
- local PoC or strong evidence,
- manual triage status,
- clear false-positive discussion.

---

## 10. Arbitrum custom detectors

Implement detector stubs and unit tests for these categories.

### 10.1 `ArbitrumBridgeDetector`

Look for:

- unauthorized `bridgeMint` / `bridgeBurn`,
- gateway-only functions callable by unexpected senders,
- direct gateway calls that bypass routers,
- incorrect L1/L2 token mapping assumptions,
- missing or inconsistent L1 counterpart checks,
- withdrawal/finalization accounting mismatch,
- WETH wrapping/unwrapping mismatch,
- unsafe custom gateway registration.

### 10.2 `CrossChainMessagingDetector`

Look for:

- unsafe cross-domain sender validation,
- missing alias handling,
- message replay assumptions,
- incorrect encoded selector/parameter handling,
- retryable ticket refund receiver hazards,
- failure paths that lock assets permanently,
- child-to-parent message finalization assumptions.

### 10.3 `UpgradeabilityDetector`

Look for:

- uninitialized implementation contracts,
- initializer re-entry/re-run risks,
- unsafe proxy admin assumptions,
- storage layout mismatch indicators,
- delegatecall hazards,
- governance/timelock execution path assumptions.

### 10.4 `AccountingDetector`

Look for:

- escrow/mint/burn supply mismatches,
- fee-on-transfer token assumptions,
- rebasing/interest-bearing token assumptions,
- non-standard ERC-20 return handling,
- rounding and decimals assumptions,
- insolvency paths.

### 10.5 `GasGriefingDetector`

Look for:

- unbounded loops over user-controlled arrays,
- gas-heavy withdrawal/finalization paths,
- griefable retryable parameters,
- inability to operate due to insufficient funds,
- gas theft or unbounded gas consumption patterns.

Each detector should initially be conservative and output `possibly_in_scope` findings that require manual triage.

---

## 11. Harness generation

Generate harnesses but do not pretend they are complete audits.

### 11.1 Foundry harnesses

Generate templates for:

- local fork read-only state setup,
- invariant tests around gateway accounting,
- access-control invariants for bridge mint/burn,
- local PoC templates that never broadcast.

### 11.2 Echidna / Medusa harnesses

Generate templates for:

- token bridge accounting invariants,
- router/gateway relationship invariants,
- custom gateway state machine fuzzing,
- role/access-control invariants.

### 11.3 Example toy bridge fixture

Include a deliberately vulnerable toy bridge fixture in `tests/fixtures/toy_bridge` so unit tests can demonstrate the detector flow safely without touching real Arbitrum contracts.

The toy fixture may include:

- an unsafe `bridgeMint`,
- a missing router check,
- a fake gateway mapping bug,
- a supply mismatch bug.

Clearly mark it as educational and not related to Arbitrum production code.

---

## 12. Reporting requirements

Create report generation for:

- Markdown human report,
- JSON machine-readable report,
- Immunefi-style bounty report template.

A report must include:

- target name,
- program URL,
- scope URL,
- scope verification timestamp,
- affected asset mapping,
- severity rationale,
- impact category,
- root cause,
- attack preconditions,
- safe local PoC steps,
- expected vs actual behavior,
- evidence attachments/artifacts,
- false-positive discussion,
- recommended remediation,
- responsible disclosure notes.

Never include exploit steps for live exploitation. Keep PoC instructions local-only.

---

## 13. Documentation requirements

Write high-quality docs:

### README.md

Explain:

- what the project is,
- what it is not,
- Arbitrum pilot target,
- safety boundaries,
- local setup,
- first commands,
- output artifacts,
- contribution style.

### docs/LOCAL_SETUP.md

Include:

- Python setup,
- `uv` setup,
- Foundry setup,
- optional analyzer installs,
- `.env.example` usage,
- local fork RPC setup,
- no private keys required.

### docs/ARBITRUM_PILOT.md

Include:

- pilot target rationale,
- scope source URLs,
- in-scope seed assets,
- out-of-scope cautions,
- recommended first analysis path,
- bridge/gateway threat model,
- how to update scope snapshot.

### docs/THREAT_MODEL_ARBITRUM.md

Include:

- L1/L2 system overview,
- bridge/gateway assets,
- trust boundaries,
- privileged roles,
- message lifecycle,
- accounting invariants,
- major failure modes,
- bounty impact mapping.

---

## 14. CI and quality gates

Create GitHub Actions:

- lint with ruff,
- type check if configured,
- run unit tests,
- check no secrets are committed,
- run basic CLI smoke tests,
- optionally run semgrep local rules.

CI must not require real RPC keys or private secrets.

---

## 15. Minimum first-commit deliverables

By the end of the first implementation pass, the repository must contain:

1. Professional README.
2. Safety and scope docs.
3. Arbitrum target config.
4. Working Python package skeleton.
5. Working CLI with at least:
   - `env doctor`,
   - `targets list`,
   - `targets show arbitrum`,
   - `scope check arbitrum`,
   - `analyze arbitrum --safe` with adapter stubs.
6. Analyzer adapter stubs with availability checks.
7. Normalized finding model.
8. Arbitrum detector stubs.
9. Toy bridge fixture.
10. Unit tests for config loading, scope gate, and finding schema.
11. Report templates.
12. `.env.example` without secrets.
13. GitHub Actions CI.
14. Commit and push attempt to `https://github.com/umutergul74/SmartContracts.git`.

---

## 16. Implementation style

Be professional and conservative.

- Prefer explicit schemas over ad-hoc dictionaries.
- Prefer deterministic artifacts over noisy output.
- Prefer modular adapters over one giant script.
- Prefer safe defaults over dangerous flexibility.
- Prefer human triage over exaggerated claims.
- Prefer explainable findings over black-box scoring.
- Keep public docs clear enough for a team member to onboard.

Do not fabricate results. If an analyzer did not run, say it did not run. If scope cannot be verified, refuse to analyze.

---

## 17. First suggested commands after implementation

Document these commands for the user:

```bash
git clone https://github.com/umutergul74/SmartContracts.git
cd SmartContracts

# Python environment
uv venv
source .venv/bin/activate
uv pip install -e '.[dev]'

# Or pip fallback
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

# Check local environment
scbounty env doctor

# Check Arbitrum target metadata and scope gate
scbounty targets show arbitrum
scbounty scope check arbitrum

# Run safe analysis with available local tools only
scbounty analyze arbitrum --safe

# Generate reports
scbounty report generate arbitrum --format markdown
scbounty report generate arbitrum --format json
```

For Windows, document the PowerShell activation equivalent.

---

## 18. Final answer Codex should provide after running

When finished, Codex should summarize:

- files created,
- commands run,
- tests passed/failed,
- tools detected/missing,
- whether the repo was pushed,
- what the next human step is.

Do not overclaim security findings in the first scaffold.
