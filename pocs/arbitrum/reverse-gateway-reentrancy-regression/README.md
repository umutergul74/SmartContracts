# Reverse gateway reentrancy regression PoC

Status: **KNOWN PUBLIC ISSUE / REGRESSION POC / NOT A BOUNTY CANDIDATE**

This local-only PoC executes the current upstream
`L2ReverseCustomGateway.outboundEscrowTransfer` flow with a callback-capable
reverse token. The sender hook reenters the L2 router before the outer
`transferFrom` updates balances.

Observed invariant violation:

- L2 tokens escrowed: `140`
- L2-to-L1 withdrawal value emitted: `180`
- L1 representation minted after processing both local messages: `180`

The outer withdrawal counts the nested transfer twice because both calls use
the same pre-transfer gateway balance.

This must not be submitted as a new vulnerability. The root cause and the same
nested balance-delta example are public in:

- ConsenSys Diligence, *Arbitrum Smart Contracts*, issue 5.1, PDF pages 14-16.
- Trail of Bits, `TOB-ARBGOV-13`, PDF pages 42-45.

The active Arbitrum One reverse gateway implementation still contains the
unguarded balance-delta code, but its only observed `TokenSet` mapping is ARB,
whose ordinary ERC20 transfer path does not provide the callback required by
this PoC. Keep this artifact as a regression test and detector fixture.

To reproduce, copy the Solidity file into upstream
`contracts/tokenbridge/test/`, copy the TypeScript test into upstream `test/`,
then run:

```text
corepack yarn hardhat test test/researchReverseGatewayReentrancy.l2.ts
```

No public-network transaction, wallet, or private key is used.
