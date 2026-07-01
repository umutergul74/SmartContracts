# Arbitrum standard gateway optional-metadata lock PoC

Status: **KNOWN PUBLIC ISSUE / REGRESSION POC / NOT A BOUNTY CANDIDATE**

This local-only PoC demonstrates a cross-chain failure in the standard ERC20 gateway
path:

1. An otherwise valid ERC20 omits the optional `name()` getter.
2. Its fallback reverts with an ordinary reason string for the unknown selector.
3. `L1ERC20Gateway.callStatic` ignores the failed `staticcall` status and forwards the
   non-empty `Error(string)` revert data as token metadata.
4. The L1 deposit succeeds and the gateway escrows the user's tokens.
5. `StandardArbERC20.bridgeInit` passes the revert data to
   `BytesParser.toString`, whose `abi.decode(input, (string))` reverts.
6. L2 proxy creation rolls back, the exact retryable remains unexecutable, and the
   already-final L1 escrow cannot be rolled back by the L2 failure.

The test uses the upstream gateway, proxy factory, beacon, standard token logic and
retryable calldata. It performs no public-network transaction.

After reproduction, duplicate review found the same root cause and stuck-token impact
in the bundled public Trail of Bits report:

- `audits/trail_of_bits_governance_report_1_6_2023.pdf`
- Finding `TOB-ARBGOV-15`
- Printed pages 47-48 (PDF pages 48-49)

This PoC is retained to test the research platform and to prevent rediscovering a known
issue as a novel bounty submission.

## Reproduce on Windows PowerShell

From this repository:

```powershell
$upstream = ".scbounty/cache/sources/arbitrum/OffchainLabs-token-bridge-contracts"
Copy-Item `
  "pocs/arbitrum/optional-metadata-revert-lock/RevertingOptionalMetadataERC20.sol" `
  "$upstream/contracts/tokenbridge/test/RevertingOptionalMetadataERC20.sol"
Copy-Item `
  "pocs/arbitrum/optional-metadata-revert-lock/researchOptionalMetadataRevertLock.l2.ts" `
  "$upstream/test/researchOptionalMetadataRevertLock.l2.ts"

Push-Location $upstream
$env:GIT_CONFIG_COUNT = "1"
$env:GIT_CONFIG_KEY_0 = "safe.directory"
$env:GIT_CONFIG_VALUE_0 = (Get-Location).Path.Replace("\", "/")
corepack yarn install --frozen-lockfile --ignore-scripts
corepack yarn hardhat test test/researchOptionalMetadataRevertLock.l2.ts
Pop-Location
```

Expected result:

```text
Research: optional metadata revert data
  1 passing
```

## Reproduce on Unix

```bash
upstream=.scbounty/cache/sources/arbitrum/OffchainLabs-token-bridge-contracts
cp pocs/arbitrum/optional-metadata-revert-lock/RevertingOptionalMetadataERC20.sol \
  "$upstream/contracts/tokenbridge/test/RevertingOptionalMetadataERC20.sol"
cp pocs/arbitrum/optional-metadata-revert-lock/researchOptionalMetadataRevertLock.l2.ts \
  "$upstream/test/researchOptionalMetadataRevertLock.l2.ts"

cd "$upstream"
corepack yarn install --frozen-lockfile --ignore-scripts
corepack yarn hardhat test test/researchOptionalMetadataRevertLock.l2.ts
```

## Evidence boundary

The behavior has been reproduced locally. Current Arbitrum One proxy/beacon reads also
show that the deployed standard gateway path points to the contracts whose verified
source contains the same `callStatic` and `BytesParser.toString` behavior. The exact
issue is already public in `TOB-ARBGOV-15`, so this artifact must not be presented as a
novel finding.
