/* eslint-env node, mocha */
import { ethers } from 'hardhat'
import { assert, expect } from 'chai'

import { applyAlias, impersonateAccount } from './testhelper'

describe('Research: optional metadata revert data', () => {
  it('escrows a valid ERC20 on L1 but makes first L2 finalization unexecutable', async () => {
    const accounts = await ethers.getSigners()
    const InboxMock = await ethers.getContractFactory('InboxMock')
    const inbox = await InboxMock.deploy()
    const L1ERC20Gateway = await ethers.getContractFactory('L1ERC20Gateway')
    const l1Gateway = await L1ERC20Gateway.deploy()

    const StandardArbERC20 = await ethers.getContractFactory('StandardArbERC20')
    const standardArbERC20Logic = await StandardArbERC20.deploy()
    const UpgradeableBeacon = await ethers.getContractFactory(
      'UpgradeableBeacon'
    )
    const beacon = await UpgradeableBeacon.deploy(standardArbERC20Logic.address)
    const BeaconProxyFactory = await ethers.getContractFactory(
      'BeaconProxyFactory'
    )
    const beaconProxyFactory = await BeaconProxyFactory.deploy()
    await beaconProxyFactory.initialize(beacon.address)

    const L2ERC20Gateway = await ethers.getContractFactory('L2ERC20Gateway')
    const l2Gateway = await L2ERC20Gateway.deploy()
    await l1Gateway.initialize(
      l2Gateway.address,
      accounts[0].address,
      inbox.address,
      await beaconProxyFactory.cloneableProxyHash(),
      beaconProxyFactory.address
    )
    await l2Gateway.initialize(
      l1Gateway.address,
      accounts[3].address,
      beaconProxyFactory.address
    )

    const OptionalMetadataToken = await ethers.getContractFactory(
      'RevertingOptionalMetadataERC20'
    )
    const l1Token = await OptionalMetadataToken.deploy()
    const tokenAmount = 10
    await l1Token.mint(accounts[0].address, tokenAmount)
    await l1Token.approve(l1Gateway.address, tokenAmount)

    let routerData = ethers.utils.defaultAbiCoder.encode(
      ['uint256', 'bytes'],
      [1, '0x']
    )
    routerData = ethers.utils.defaultAbiCoder.encode(
      ['address', 'bytes'],
      [accounts[0].address, routerData]
    )
    const depositTx = await l1Gateway.outboundTransfer(
      l1Token.address,
      accounts[0].address,
      tokenAmount,
      100,
      2,
      routerData,
      { value: 201 }
    )
    const depositReceipt = await depositTx.wait()
    assert.equal(
      (await l1Token.balanceOf(l1Gateway.address)).toString(),
      tokenAmount.toString(),
      'L1 gateway must retain the escrow after the L1 deposit transaction'
    )

    const retryableTopic = inbox.interface.getEventTopic(
      'InboxRetryableTicket'
    )
    const retryableLog = depositReceipt.logs.find(
      log => log.topics[0] === retryableTopic
    )
    if (!retryableLog) throw new Error('retryable event not found')
    const retryable = inbox.interface.parseLog(retryableLog)
    const finalizedDeposit = l2Gateway.interface.decodeFunctionData(
      'finalizeInboundTransfer',
      retryable.args.data
    )
    const [deployData] = ethers.utils.defaultAbiCoder.decode(
      ['bytes', 'bytes'],
      finalizedDeposit._data
    )
    const [nameResult] = ethers.utils.defaultAbiCoder.decode(
      ['bytes', 'bytes', 'bytes'],
      deployData
    )
    assert.equal(
      nameResult.slice(0, 10),
      '0x08c379a0',
      'L1 gateway must forward Error(string) revert data as if it were metadata'
    )

    const expectedL2Token = await l2Gateway
      .connect(accounts[3])
      .calculateL2TokenAddress(l1Token.address)
    assert.equal(await ethers.provider.getCode(expectedL2Token), '0x')

    const aliasedL1Gateway = await impersonateAccount(
      applyAlias(l1Gateway.address)
    )
    for (let attempt = 0; attempt < 2; attempt++) {
      await expect(
        aliasedL1Gateway.sendTransaction({
          to: retryable.args.to,
          data: retryable.args.data,
          value: retryable.args.value,
        })
      ).to.be.reverted
    }

    assert.equal(
      await ethers.provider.getCode(expectedL2Token),
      '0x',
      'failed metadata parsing must roll back the CREATE2 proxy deployment'
    )
    assert.equal(
      (await l1Token.balanceOf(l1Gateway.address)).toString(),
      tokenAmount.toString(),
      'L2 retryable failure cannot roll back the already-final L1 escrow'
    )
  })
})
