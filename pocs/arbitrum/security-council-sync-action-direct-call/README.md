# Security council sync action direct-call review

> DRAFT / NOT A VALIDATED BOUNTY FINDING.

This local-only model documents a triage branch for
`ArbitrumFoundation/governance/src/security-council-mgmt/SecurityCouncilMemberSyncAction.sol`.

The reviewed source has an external `perform(address,address[],uint256)` entry point and updates a
Gnosis Safe through `execTransactionFromModule`. At first glance that looks dangerous: if the action
contract itself were an enabled Safe module, any caller could try to replace the Safe owners.

The current evidence points the other way:

- upstream tests deploy the Safe with `UpgradeExecutor` as the enabled module, not the action
  contract;
- deployment scripts pass the configured executor as the Safe module;
- `SecurityCouncilMemberSyncAction` is documented as an action expected to be delegatecalled by an
  Upgrade Executor;
- a direct call reaches `execTransactionFromModule` with the action contract as `msg.sender`, which
  is not the enabled module in the intended setup.

The accompanying Foundry model proves the expected control split:

- `UpgradeExecutor.execute(action, data)` succeeds because the action runs by delegatecall and the
  Safe sees the executor module;
- `action.perform(...)` called directly fails and leaves owners unchanged.

This is kept as a regression/research note because the pattern is subtle and worth rechecking
against deployed module lists when read-only RPC metadata is available.

