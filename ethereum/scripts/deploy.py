from brownie import Contract, OmniPool, LendingPortal, MockToken, DiamondCutFacet, DiamondLoupeFacet, GovernanceFacet, \
    OwnershipFacet, WormholeFacet, DolaDiamond

from brownie import network
from brownie.network import priority_fee

from scripts.helpful_scripts import get_account, get_register_data, get_wormhole, get_wormhole_chain_id, zero_address


def deploy():
    account = get_account()
    if network.show_active() in ["rinkeby", "goerli"]:
        priority_fee("1 gwei")
    deploy_facets = [DiamondCutFacet, DiamondLoupeFacet, GovernanceFacet,
                     OwnershipFacet, WormholeFacet]
    for facet in deploy_facets:
        print(f"deploy {facet._name}...")
        facet.deploy({'from': account})

    print("deploy DolaDiamond...")
    register_data = get_register_data(deploy_facets)
    DolaDiamond.deploy(
        register_data, [account.address, zero_address(), b"", get_wormhole(),
                        get_wormhole_chain_id(), 1, zero_address()], {'from': account})

    deploy_omnipool("USDT", account)
    deploy_omnipool("BTC", account)

    print("deploy LendingPortal...")
    LendingPortal.deploy(DolaDiamond[-1], {'from': account})


def deploy_omnipool(token, account):

    print(f"deploy {token}...")
    MockToken.deploy(token, token, {'from': account})
    print(f"deploy {token} omnipool...")
    OmniPool.deploy(DolaDiamond[-1].address,
                    MockToken[-1].address, {'from': account})

    print(f"add {token} omnipool")
    wormhole_facet = Contract.from_abi(
        "WormholeFacet", DolaDiamond[-1].address, WormholeFacet.abi)
    wormhole_facet.addOmniPool(OmniPool[-1].address, {'from': account})