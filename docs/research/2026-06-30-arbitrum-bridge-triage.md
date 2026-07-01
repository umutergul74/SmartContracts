# Arbitrum bridge/gateway triage log - 2026-06-30

Status: **DRAFT / NOT A VALIDATED BOUNTY FINDING**

This note records manual triage and platform improvements from local-only Arbitrum
bridge/gateway research. It is not an Immunefi report and must not be submitted as a
validated vulnerability without confirmed scope, impact mapping, and a local PoC or
equivalent strong evidence.

## Runs reviewed

- Semgrep + internal run:
  `artifacts/runs/arbitrum-20260630T210645Z-a408545a`
- Slither + internal run:
  `artifacts/runs/arbitrum-20260630T211533Z-a408545a`
- Latest Semgrep + internal regression run after detector-noise reduction:
  `artifacts/runs/arbitrum-20260701T083736722887Z-26c7eb30`
  - Semgrep completed for both selected Arbitrum repositories.
  - Internal detectors completed.
  - Review queue was reduced to 3 non-promoted findings: the known optional metadata
    issue plus two low-confidence counterpart-gated liveness loops.
- Latest Slither degraded-mode run:
  `artifacts/runs/arbitrum-20260701T084153351457Z-26c7eb30`
  - Slither timed out on the selected upstream repositories and returned structured
    analyzer failures instead of aborting the whole pipeline.
  - Internal detectors continued and produced the same 3 review-only findings.
- Live scope attestation:
  `artifacts/scope/arbitrum/20260630T222143Z.json`
  - 181 smart-contract asset rows
  - 13 in-scope impacts
  - exact reviewed snapshot match
  - scope hash:
    `e22d5a917fa11afcd863cc070a994a640856bf66d82245c97c884d08f542d6ce`

## Tooling result

- Upstream `OffchainLabs/token-bridge-contracts` dependencies were installed in the
  ignored cache with `yarn install --frozen-lockfile --ignore-scripts`.
- `hardhat compile` succeeded for `OffchainLabs/token-bridge-contracts` after passing
  a command-local Git `safe.directory` setting.
- Slither 0.11.5 produced JSON for `OffchainLabs/token-bridge-contracts`.
- Slither returned a silent `exit 1` for `OffchainLabs/nitro-contracts`; no JSON,
  stdout, or stderr was produced. Treat Nitro Slither coverage as degraded for this
  run.
- The target mapping originally selected only 12 token-bridge files even though the
  live bridge scope contains 43 paths in `OffchainLabs/token-bridge-contracts`.
  The reviewed bridge profile now selects all 43 token-bridge paths plus 15
  bridge-focused Nitro paths.
- Source acquisition now fails closed if even one configured reviewed path is missing;
  it no longer silently analyzes a partial subset.
- Local CI-style verification was green after the toy bridge invariant stabilization:
  Ruff, mypy, pytest, Semgrep rule validation, and Foundry fixture tests passed locally.
  The current GitHub Actions run for commit `80efd62` also completed successfully.

## Internal detector refinement

The first Arbitrum run produced noisy cross-chain and gateway-mapping signals because
the textual guard detector did not recognize `onlyCounterpartGateway`.

The detector was refined to recognize counterpart/cross-domain guard markers such as:

- `onlyCounterpartGateway`
- bridge/outbox sender checks
- address alias helper checks

After this, the Arbitrum Semgrep + internal run dropped from 9 review findings to 6.
The remaining internal findings are low-confidence review items rather than validated
bugs.

The analyzer evidence path was also corrected so Slither/Semgrep findings are admitted
only when their source location exactly matches a selected path for that repository.
This prevents whole-repository compilation from importing out-of-profile findings.

Follow-up noise-reduction changes added explicit handling for:

- revert-only bridge-token stubs, so abstract placeholder `bridgeMint` / `bridgeBurn`
  methods are not treated as reachable missing-access-control bugs;
- typed `AlreadyInit` / non-zero bridge initializer guards;
- known Arbitrum guarded initializer chains such as `TokenGateway._initialize`,
  `L1ArbitrumGateway._initialize`, `L2ArbitrumGateway._initialize`,
  `GatewayRouter._initialize`, and `L2GatewayToken._initialize`;
- internal/private/admin-only loop paths, so they are not elevated to public
  user-controlled gas-griefing signals;
- matching Semgrep exclusions for revert-only stubs and already-initialized guards.

## Manual triage notes

### Known issue reproduced: optional ERC20 metadata revert data locks the first deposit

Status: **technically reproduced, but rejected as a new bounty candidate because it is
publicly documented as Trail of Bits finding `TOB-ARBGOV-15`**.

#### Root cause

The standard bridge attempts to support ERC20 metadata compatibility, including absent
getters and legacy `bytes32` metadata. The following cross-chain sequence is unsafe:

1. `L1ERC20Gateway.callStatic` performs a metadata `staticcall` but discards its
   success flag and returns the raw bytes for both success and failure.
2. `getOutboundCalldata` embeds those raw bytes for `name()`, `symbol()` and
   `decimals()` in the retryable payload.
3. An otherwise valid ERC20 can omit the optional `name()` getter and revert with an
   ordinary reason string for an unknown selector.
4. The failed L1 call therefore contributes non-empty ABI `Error(string)` bytes,
   beginning with selector `0x08c379a0`, rather than empty "getter unavailable" data.
5. On L2, `StandardArbERC20.bridgeInit` passes those bytes to
   `BytesParser.toString`.
6. `BytesParser.toString` executes `abi.decode(input, (string))`, which reverts for
   the `Error(string)` payload.
7. `L2ERC20Gateway.handleNoContract` cannot complete proxy initialization, so the
   CREATE2 deployment rolls back and the retryable remains unexecutable.
8. The successful L1 deposit transaction already escrowed the user's tokens and
   cannot be rolled back by the later L2 failure.

Relevant live-scope paths:

- `contracts/tokenbridge/ethereum/gateway/L1ERC20Gateway.sol`
- `contracts/tokenbridge/arbitrum/gateway/L2ERC20Gateway.sol`
- `contracts/tokenbridge/arbitrum/StandardArbERC20.sol`
- `contracts/tokenbridge/libraries/BytesParser.sol`
- `contracts/tokenbridge/libraries/ClonableBeaconProxy.sol`

#### Local proof

Committed PoC:

`pocs/arbitrum/optional-metadata-revert-lock/`

The PoC deploys the real upstream L1/L2 gateways, inbox mock, beacon, proxy factory and
standard L2 token logic. Its L1 token implements the required ERC20 surface, exposes
valid `symbol()` and `decimals()`, omits optional `name()`, and uses a normal
reason-string revert for unknown selectors.

Observed assertions:

- L1 deposit succeeds.
- L1 gateway balance increases by the full deposited amount.
- Retryable metadata contains `Error(string)` selector `0x08c379a0`.
- The exact retryable calldata reverts on two independent execution attempts.
- The expected CREATE2 L2 token address remains code-free.
- L1 escrow remains unchanged after both L2 failures.

Local result:

```text
Research: optional metadata revert data
  1 passing
```

#### Read-only deployed-path verification

No transaction was sent. Read-only RPC and verified-source checks showed:

- Ethereum block `25433482`:
  - L1 standard gateway proxy:
    `0xa3A7B6F88361F48403514059F1F16C8E78d60EeC`
  - active implementation:
    `0xb4299A1F5f26fF6a98B7BA35572290C359fde900`
  - counterpart:
    `0x09e9222E96E7B4AE2a407B98d48e330053351EEe`
  - L2 beacon proxy factory:
    `0x3fE38087A94903A9D946fa1915e1772fe611000f`
- Arbitrum One block `479067245`:
  - L2 standard gateway:
    `0x09e9222E96E7B4AE2a407B98d48e330053351EEe`
  - beacon:
    `0xE72ba9418b5f2Ce0A6a40501Fe77c6839Aa37333`
  - active standard-token implementation:
    `0x3f770Ac673856F105b586bb393d122721265aD46`

The verified deployed L1 source contains the success-discarding `callStatic` logic, and
the verified deployed standard-token source contains the same reverting
`BytesParser.toString` path.

#### Impact and remaining rejection risk

The technical impact is a first-deposit lock for a token whose optional string metadata
getter is absent/reverting with data: tokens remain in L1 escrow while the associated
L2 finalization cannot deploy or initialize the standard representation. Recovery
requires a gateway/token-logic upgrade or another privileged intervention.

This is stronger than a deliberately malformed return-value example because ERC20
`name`, `symbol`, and `decimals` are optional metadata methods.

Duplicate/known-issue review found an exact public match:

- Audit:
  `audits/trail_of_bits_governance_report_1_6_2023.pdf`
- Finding:
  `TOB-ARBGOV-15 - Lack of contract existence checks in the gateway may not detect
  failed execution`
- Printed pages:
  47-48 (PDF pages 48-49)
- The report explicitly states that failed parsing can leave tokens stuck in
  `L1ERC20Gateway` and reproduces the same `callStatic` and `bridgeInit` paths.

Current decision: **do not submit**. Keep the PoC as a regression fixture and keep the
detector as a known-pattern signal, but exclude this issue from the novel-candidate
queue.

### Cross-chain sender validation and gateway mapping

Initial alarms around:

- `L1ArbitrumGateway.finalizeInboundTransfer`
- `L2ArbitrumGateway.finalizeInboundTransfer`
- `L2GatewayRouter.setGateway`

were not promoted. The relevant functions are guarded by `onlyCounterpartGateway`.
On L1 this validates the bridge caller and L2-to-L1 sender. On L2 this validates the
aliased L1 counterpart gateway.

Current status: **rejected as current bug candidates**.

### Known issue reproduced: reverse-gateway nested withdrawal over-accounting

Status: **technically reproduced, but rejected as a new bounty candidate because
the reentrancy/accounting root cause is already public**.

The current upstream `L2ReverseCustomGateway` measures its own token balance,
calls `safeTransferFrom`, and then returns the full balance delta. It does not
use a reentrancy guard. A callback-capable token can notify the sender before
the outer transfer mutates balances. The sender then starts a nested withdrawal.

Local proof:

`pocs/arbitrum/reverse-gateway-reentrancy-regression/`

Observed assertions:

- The holder supplies 140 L2 tokens in total.
- The nested withdrawal emits 40.
- The outer withdrawal emits 140 because its initial balance snapshot predates
  the nested transfer.
- The L2 gateway therefore escrows 140 while L2-to-L1 messages encode 180.
- Processing both local messages mints 180 L1 representation tokens.

Duplicate review found the same vulnerability class and nearly identical
numeric example in:

- ConsenSys Diligence, *Arbitrum Smart Contracts*, issue 5.1, PDF pages 14-16.
  It describes callback reentrancy causing 100 escrowed tokens to mint 150 and
  explicitly recommends L1 and L2 reentrancy guards.
- Trail of Bits, `TOB-ARBGOV-13`, PDF pages 42-45. It documents callback-driven
  reverse/custom gateway over-accounting and recommends tracking the gateway
  balance as one possible remediation.

Read-only deployment checks found that Arbitrum One reverse gateway proxy
`0xCaD7828a19b363A2B44717AFB1786B5196974D8E` currently points to verified
`L2ReverseCustomGateway` implementation
`0x5d96786d3eb13cad05c9fd7d0f7bb9560b4e5056`, whose source still has the
unguarded balance-delta sequence. Its observed `TokenSet` history contains one
mapping, from L1 ARB to L2 ARB. That ordinary ERC20 path does not expose the
callback used by this PoC.

Current decision: **do not submit**. Preserve it as a regression fixture and a
high-signal detector case, but exclude it from the novel-candidate queue.

### Known behavior: ERC20 Inbox prefunded native-token balance can fund a later deposit

Status: **rejected as a new bounty candidate because the behavior is explicitly
implemented, commented, and covered by upstream tests**.

The ERC20-native Orbit inbox checks its own native-token balance before pulling tokens
from the caller:

- `src/bridge/ERC20Inbox.sol`
- `_deliverToBridge(...)`
- if the inbox already holds at least `tokenAmount`, no `safeTransferFrom(msg.sender, ...)`
  is performed;
- the bridge then pulls the approved inbox balance and enqueues the delayed message.

This initially looked like a possible ambient-balance consumption bug: if a third party
or previous flow leaves native tokens on the inbox, a later caller can submit
`depositERC20(amount)` without their own tokens being transferred.

Manual review found that this is intentional for ERC20-native retryable flows. The
source comment states that the inbox may have been pre-funded in a prior call as part of
token bridging. Upstream Foundry test
`test/foundry/ERC20Inbox.t.sol::test_depositERC20_FromEOA_InboxPrefunded` explicitly
mints native tokens to the inbox, calls `depositERC20` as a user, and asserts the user's
token balance is unchanged while the bridge balance increases.

Current decision: **do not submit** unless a later, separate proof shows that an
ordinary protocol path can leave another user's pre-funded balance available across
transactions without that being merely a direct token donation or intended gateway
prefunding.

### Known public dispute/report: delay-buffer accounting differs for force inclusion

Status: **technically reproduced locally, but rejected as a new bounty candidate because
the same force-inclusion delay-buffer inconsistency is already public in the 2024
Code4rena Arbitrum Foundation findings**.

A targeted local Hardhat regression showed that force-including delayed messages can
anchor delay-buffer updates differently from the normal delayed-message proof path:

- normal delay-proof logic anchors on the first unread delayed message in the batch;
- the force-inclusion path can anchor on the force-included message being appended;
- the result preserves more delay buffer than the normal path for an equivalent batch.

Read-only deployment checks showed Arbitrum One and Nova sequencer inbox proxies both
pointing to implementation `0x98a58ADAb0f8A66A1BF4544d804bc0475dff32c7`, with
`isDelayBufferable() == true` and a live maximum buffer of 14,400 blocks.

Duplicate review found Code4rena issue `#55`, selected as medium issue `M-01`, titled
“Inconsistent sequencer unexpected delay in DelayBuffer may harm users calling
forceInclusion()”. The sponsor disputed it publicly, but it is still not a novel
private bounty candidate.

Current decision: **do not submit**. Keep the local regression as a research note and
possible future platform fixture, not as a report candidate.

### Initializer review

Remaining initializer findings are low-confidence because the public initializer entry
points delegate to internal initializer functions instead of using an OpenZeppelin
`initializer` modifier directly.

Observed guard path:

- `L2ERC20Gateway.initialize`
- `L2CustomGateway.initialize`
- `L2WethGateway.initialize`
- `L2GatewayRouter.initialize`
- internal path reaches `TokenGateway._initialize`
- `TokenGateway._initialize` requires `counterpartGateway == address(0)` and reverts
  with `ALREADY_INIT` once initialized.

Current status: **needs deployed-proxy initialization verification, not a validated
code vulnerability**.

### Gas/liveness collection loops

Remaining low-confidence gas/liveness signals:

- `L2GatewayRouter.setGateway`
- `L2CustomGateway.registerTokenFromL1`

Manual L1 source review found that ordinary trustless user paths encode a single
token/gateway pair. Bulk array paths are owner-controlled:

- `L1GatewayRouter.setGateway(...)` creates arrays of length 1 for trustless token
  self-registration.
- `L1CustomGateway.registerTokenToL2(...)` creates arrays of length 1 for trustless
  custom token registration.
- bulk `setGateways` / `forceRegisterTokenToL2` style paths are owner-only.

Current status: **low-priority liveness review, not a strong bounty candidate**.

### Slither numeric rounding signal

Slither flagged `_getScaledAmount` in `L1AtomicTokenBridgeCreator` as
divide-before-multiply. Manual review shows the code intentionally rounds up after
division when token decimals are below 18.

Current status: **rejected as a current bug candidate**.

### Slither USDC mint unused-return signal

Slither flagged `L2USDCGateway.inboundEscrowTransfer` for ignoring the bool returned by
`IFiatToken.mint`.

Manual dependency review of `@offchainlabs/stablecoin-evm` shows the referenced FiatToken
implementation enforces success with `require` checks and returns `true` after minting.
The ignored bool is therefore not enough for an exploit claim against the bundled
implementation.

Current status: **not promoted; keep as compatibility-hardening note only**.

### Slither retryable / arbitrary send signals

Retryable and arbitrary-send findings in `L1AtomicTokenBridgeCreator` and
`L1TokenBridgeRetryableSender` were emitted because Slither compiled the whole
repository. Those paths were not in the selected bridge profile. The pipeline now
filters analyzer output to exact selected paths, so these signals are no longer admitted
as profile findings. Manual read also showed that the value transfers are expected
retryable funding/deployer refund flows and that the sender contract is `onlyOwner`
gated.

Current status: **rejected for this profile unless the selected live-scope mapping is
explicitly expanded**.

## Next research steps

1. Add deployed-proxy metadata verification to the platform using read-only RPC
   manifests rather than ad hoc research commands.
2. Investigate retryable refund receiver flows specifically:
   - excess fee refund address
   - call value refund address
   - resend / expired retryable recovery
3. Continue with Nitro using either a fixed Slither invocation or targeted Foundry/Hardhat
   harnesses, since Slither produced no JSON for Nitro in this run.
4. Before promoting any future candidate, search both public issue trackers and bundled
   audit PDFs for exact source-path/root-cause matches.
