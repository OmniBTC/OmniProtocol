import functools
from typing import List

import requests
# 1e27
from sui_brownie import SuiObject, Argument, U16, NestedResult

from dola_sui_sdk import load, sui_project

RAY = 1000000000000000000000000000


def vote_create_pool(coin_type, decimal=8):
    """
    public entry fun vote_create_omnipool<CoinType>(
        governance_info: &mut GovernanceInfo,
        proposal: &mut Proposal<Certificate>,
        decimals: u8,
        ctx: &mut TxContext
    )
    :param decimal:
    :param coin_type:
    :return:
    """
    genesis_proposal = load.genesis_proposal_package()
    governance = load.governance_package()

    genesis_proposal.genesis_proposal.vote_create_omnipool(
        governance.governance_v1.GovernanceInfo[-1],
        sui_project[SuiObject.from_type(proposal())][-1],
        decimal,
        type_arguments=[coin_type]
    )


def init_wormhole():
    """
    public entry fun complete(
        deployer: DeployerCap,
        upgrade_cap: UpgradeCap,
        governance_chain: u16,
        governance_contract: vector<u8>,
        initial_guardians: vector<vector<u8>>,
        guardian_set_epochs_to_live: u32,
        message_fee: u64,
        ctx: &mut TxContext
    )
    :return:
    """
    wormhole = load.wormhole_package()
    upgrade_cap = load.get_upgrade_cap_by_package_id(wormhole.package_id)

    wormhole.setup.complete(
        wormhole.setup.DeployerCap[-1],
        upgrade_cap,
        0,
        list(bytes.fromhex("deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef")),
        [
            list(bytes.fromhex("1337133713371337133713371337133713371337")),
            list(bytes.fromhex("c0dec0dec0dec0dec0dec0dec0dec0dec0dec0de")),
            list(bytes.fromhex("ba5edba5edba5edba5edba5edba5edba5edba5ed"))
        ],
        0,
        0
    )


def register_token_price(dola_pool_id, price, decimal):
    """
    public entry fun register_token_price(
        _: &OracleCap,
        price_oracle: &mut PriceOracle,
        dola_pool_id: u16,
        token_price: u64,
        price_decimal: u8
    )
    :return:
    """
    dola_protocol = load.dola_protocol_package()

    dola_protocol.oracle.register_token_price(
        dola_protocol.oracle.OracleCap[-1],
        dola_protocol.oracle.PriceOracle[-1],
        dola_pool_id,
        price,
        decimal
    )


def active_governance_v1():
    """Calls are required by the deployer
    public entry fun activate_governance(
        governance_genesis: &mut GovernanceGenesis,
        governance_info: &mut GovernanceInfo,
        ctx: &mut TxContext
    )
    :return:
    """
    dola_protocol = load.dola_protocol_package()
    upgrade_cap = load.get_upgrade_cap_by_package_id(dola_protocol.package_id)
    dola_protocol.governance_v1.activate_governance(
        upgrade_cap,
        dola_protocol.governance_v1.GovernanceInfo[-1],
    )


def init_wormhole_adapter_pool():
    """
    public entry fun initialize(
        pool_genesis: &mut PoolGenesis,
        sui_wormhole_chain: u16, // Represents the wormhole chain id of the wormhole adpter core on Sui
        sui_wormhole_address: vector<u8>, // Represents the wormhole contract address of the wormhole adpter core on Sui
        wormhole_state: &mut WormholeState,
        ctx: &mut TxContext
    )
    :return:
    """
    dola_protocol = load.dola_protocol_package()
    wormhole = load.wormhole_package()

    dola_protocol.wormhole_adapter_pool.initialize(
        dola_protocol.wormhole_adapter_pool.PoolGenesis[-1],
        0,
        get_wormhole_adapter_core_emitter(),
        wormhole.state.State[-1]
    )


def register_owner(vaa):
    """
    public entry fun register_owner(
        pool_state: &PoolState,
        pool_approval: &mut PoolApproval,
        vaa: vector<u8>
    )
    :return:
    """
    omnipool = load.omnipool_package()

    omnipool.wormhole_adapter_pool.register_owner(
        omnipool.wormhole_adapter_pool.PoolState[-1],
        omnipool.dola_pool.PoolApproval[-1],
        vaa
    )


def delete_owner(vaa):
    """
    public entry fun delete_owner(
        pool_state: &PoolState,
        pool_approval: &mut PoolApproval,
        vaa: vector<u8>
    )
    :return:
    """
    omnipool = load.omnipool_package()

    omnipool.wormhole_adapter_pool.delete_owner(
        omnipool.wormhole_adapter_pool.PoolState[-1],
        omnipool.dola_pool.PoolApproval[-1],
        vaa
    )


def register_spender(vaa):
    """
    public entry fun register_spender(
        pool_state: &PoolState,
        pool_approval: &mut PoolApproval,
        vaa: vector<u8>
    )
    :return:
    """
    dola_protocol = load.dola_protocol_package()

    dola_protocol.wormhole_adapter_pool.register_spender(
        dola_protocol.wormhole_adapter_pool.PoolState[-1],
        dola_protocol.dola_pool.PoolApproval[-1],
        list(bytes.fromhex(vaa.replace("0x", "")))
    )


def delete_spender(vaa):
    """
    public entry fun delete_spender(
        pool_state: &PoolState,
        pool_approval: &mut PoolApproval,
        vaa: vector<u8>
    )
    :return:
    """
    omnipool = load.omnipool_package()

    omnipool.wormhole_adapter_pool.delete_spender(
        omnipool.wormhole_adapter_pool.PoolState[-1],
        omnipool.dola_pool.PoolApproval[-1],
        vaa
    )


def create_proposal():
    """
    public entry fun create_proposal(governance_info: &mut GovernanceInfo, ctx: &mut TxContext)
    :return:
    """
    genesis_proposal = load.genesis_proposal_package()
    dola_protocol = load.dola_protocol_package()
    genesis_proposal.genesis_proposal.create_proposal(
        dola_protocol.governance_v1.GovernanceInfo[-1])


def vote_init_wormhole_adapter_core():
    """
    public entry fun vote_init_wormhole_adapter_core(
        governance_info: &mut GovernanceInfo,
        proposal: &mut Proposal<Certificate>,
        wormhole_state: &mut State,
        ctx: &mut TxContext
    )
    :return:
    """
    genesis_proposal = load.genesis_proposal_package()
    governance = load.governance_package()
    wormhole = load.wormhole_package()

    genesis_proposal.genesis_proposal.vote_init_wormhole_adapter_core(
        governance.governance_v1.GovernanceInfo[-1],
        sui_project[SuiObject.from_type(proposal())][-1],
        wormhole.state.State[-1]
    )


def vote_init_lending_core():
    """
    public entry fun vote_init_lending_core(
        governance_info: &mut GovernanceInfo,
        proposal: &mut Proposal<Certificate>,
        total_app_info: &mut TotalAppInfo,
        ctx: &mut TxContext
    )
    :return:
    """
    genesis_proposal = load.genesis_proposal_package()
    app_manager = load.app_manager_package()
    governance = load.governance_package()

    genesis_proposal.genesis_proposal.vote_init_lending_core(
        governance.governance_v1.GovernanceInfo[-1],
        sui_project[SuiObject.from_type(proposal())][-1],
        app_manager.app_manager.TotalAppInfo[-1],
    )


def vote_init_system_core():
    """
    public entry fun vote_init_system_core(
        governance_info: &mut GovernanceInfo,
        proposal: &mut Proposal<Certificate>,
        total_app_info: &mut TotalAppInfo,
        ctx: &mut TxContext
    )
    :return:
    """
    genesis_proposal = load.genesis_proposal_package()
    app_manager = load.app_manager_package()
    governance = load.governance_package()

    genesis_proposal.genesis_proposal.vote_init_system_core(
        governance.governance_v1.GovernanceInfo[-1],
        sui_project[SuiObject.from_type(proposal())][-1],
        app_manager.app_manager.TotalAppInfo[-1],
    )


def vote_init_dola_portal():
    """
    public entry fun vote_init_dola_portal(
        governance_info: &mut GovernanceInfo,
        proposal: &mut Proposal<Certificate>,
        dola_contract_registry: &mut DolaContractRegistry,
        ctx: &mut TxContext
    )
    :return:
    """
    genesis_proposal = load.genesis_proposal_package()
    governance = load.governance_package()
    dola_types = load.dola_types_package()

    genesis_proposal.genesis_proposal.vote_init_dola_portal(
        governance.governance_v1.GovernanceInfo[-1],
        sui_project[SuiObject.from_type(proposal())][-1],
        dola_types.dola_contract.DolaContractRegistry[-1]
    )


def vote_init_chain_group_id(group_id, chain_ids):
    """
    public entry fun vote_init_chain_group_id(
        governance_info: &mut GovernanceInfo,
        proposal: &mut Proposal<Certificate>,
        user_manager: &mut UserManagerInfo,
        group_id: u16,
        chain_ids: vector<u16>,
        ctx: &mut TxContext
    )
    :return:
    """
    genesis_proposal = load.genesis_proposal_package()
    governance = load.governance_package()
    user_manager = load.user_manager_package()
    genesis_proposal.genesis_proposal.vote_init_chain_group_id(
        governance.governance_v1.GovernanceInfo[-1],
        sui_project[SuiObject.from_type(proposal())][-1],
        user_manager.user_manager.UserManagerInfo[-1],
        group_id,
        chain_ids
    )


def vote_remote_register_owner(dola_chain_id, dola_contract):
    """
    public entry fun vote_remote_register_owner(
        governance_info: &mut GovernanceInfo,
        proposal: &mut Proposal<Certificate>,
        wormhole_state: &mut State,
        core_state: &mut CoreState,
        dola_chain_id: u16,
        dola_contract: u256,
        wormhole_message_fee: Coin<SUI>,
        ctx: &mut TxContext
    )
    :return:
    """
    genesis_proposal = load.genesis_proposal_package()
    governance = load.governance_package()
    wormhole = load.wormhole_package()
    wormhole_adapter_core = load.wormhole_adapter_core_package()

    genesis_proposal.genesis_proposal.vote_remote_register_owner(
        governance.governance_v1.GovernanceInfo[-1],
        sui_project[SuiObject.from_type(proposal())][-1],
        wormhole.state.State[-1],
        wormhole_adapter_core.wormhole_adapter_core.CoreState[-1],
        dola_chain_id,
        dola_contract,
        0
    )


def vote_remote_delete_owner(dola_chain_id, dola_contract):
    """
    public entry fun vote_remote_delete_owner(
        governance_info: &mut GovernanceInfo,
        proposal: &mut Proposal<Certificate>,
        wormhole_state: &mut State,
        core_state: &mut CoreState,
        dola_chain_id: u16,
        dola_contract: u256,
        wormhole_message_fee: Coin<SUI>,
        ctx: &mut TxContext
    )
    :return:
    """
    genesis_proposal = load.genesis_proposal_package()
    governance = load.governance_package()
    wormhole = load.wormhole_package()
    wormhole_adapter_core = load.wormhole_adapter_core_package()

    genesis_proposal.genesis_proposal.vote_remote_delete_owner(
        governance.governance_v1.GovernanceInfo[-1],
        sui_project[SuiObject.from_type(proposal())][-1],
        wormhole.state.State[-1],
        wormhole_adapter_core.wormhole_adapter_core.CoreState[-1],
        dola_chain_id,
        dola_contract,
        0
    )


def vote_remote_register_spender(dola_chain_id, dola_contract):
    """
    public entry fun vote_remote_register_spender(
        governance_info: &mut GovernanceInfo,
        proposal: &mut Proposal<Certificate>,
        wormhole_state: &mut State,
        core_state: &mut CoreState,
        dola_chain_id: u16,
        dola_contract: u256,
        wormhole_message_fee: Coin<SUI>,
        ctx: &mut TxContext
    )
    :return:
    """
    genesis_proposal = load.genesis_proposal_package()
    wormhole = load.wormhole_package()
    dola_protocol = load.dola_protocol_package()

    result = sui_project.pay_sui([0])
    zero_coin = result['objectChanges'][-1]['objectId']

    genesis_proposal.genesis_proposal.vote_remote_register_spender(
        dola_protocol.governance_v1.GovernanceInfo[-1],
        sui_project[SuiObject.from_type(proposal())][-1],
        wormhole.state.State[-1],
        dola_protocol.wormhole_adapter_core.CoreState[-1],
        dola_chain_id,
        dola_contract,
        zero_coin
    )


def vote_remote_delete_spender(dola_chain_id, dola_contract):
    """
    public entry fun vote_remote_delete_spender(
        governance_info: &mut GovernanceInfo,
        proposal: &mut Proposal<Certificate>,
        wormhole_state: &mut State,
        core_state: &mut CoreState,
        dola_chain_id: u16,
        dola_contract: u256,
        wormhole_message_fee: Coin<SUI>,
        ctx: &mut TxContext
    )
    :return:
    """
    genesis_proposal = load.genesis_proposal_package()
    governance = load.governance_package()
    wormhole = load.wormhole_package()
    wormhole_adapter_core = load.wormhole_adapter_core_package()

    genesis_proposal.genesis_proposal.vote_remote_delete_spender(
        governance.governance_v1.GovernanceInfo[-1],
        sui_project[SuiObject.from_type(proposal())][-1],
        wormhole.state.State[-1],
        wormhole_adapter_core.wormhole_adapter_core.CoreState[-1],
        dola_chain_id,
        dola_contract,
        0
    )


def vote_register_new_pool(pool_id, pool_name, coin_type, dst_chain=0):
    """
    public entry fun vote_register_new_pool(
        governance_info: &mut GovernanceInfo,
        proposal: &mut Proposal<Certificate>,
        pool_manager_info: &mut PoolManagerInfo,
        pool_dola_address: vector<u8>,
        pool_dola_chain_id: u16,
        dola_pool_name: vector<u8>,
        dola_pool_id: u16,
        weight: u256,
        ctx: &mut TxContext
    )
    :return:
    """
    if isinstance(coin_type, str):
        if "0x" in coin_type[:2] and dst_chain != 1:
            coin_type = coin_type[2:]

        if dst_chain not in [0, 1]:
            coin_type = coin_type.lower()

        if dst_chain in [0, 1]:
            coin_type = list(bytes(coin_type, "ascii"))
        else:
            # for eth, use hex string
            coin_type = list(bytes.fromhex(coin_type))
    genesis_proposal = load.genesis_proposal_package()
    governance = load.governance_package()
    pool_manager = load.pool_manager_package()
    genesis_proposal.genesis_proposal.vote_register_new_pool(
        governance.governance_v1.GovernanceInfo[-1],
        sui_project[SuiObject.from_type(proposal())][-1],
        pool_manager.pool_manager.PoolManagerInfo[-1],
        coin_type,
        dst_chain,
        list(pool_name),
        pool_id,
        1
    )


def claim_test_coin(coin_type):
    test_coins = load.test_coins_package()
    test_coins.faucet.claim(
        test_coins.faucet.Faucet[-1],
        type_arguments=[coin_type]
    )


def force_claim_test_coin(coin_type, amount):
    test_coins = load.test_coins_package()
    test_coins.faucet.force_claim(
        test_coins.faucet.Faucet[-1],
        int(amount),
        type_arguments=[coin_type]
    )


def add_test_coins_admin(address):
    test_coins = load.test_coins_package()
    test_coins.faucet.add_admin(
        test_coins.faucet.Faucet[-1],
        address,
    )


def usdt():
    return f"{sui_project.TestCoins[-1]}::coins::USDT"


def usdc():
    return f"{sui_project.TestCoins[-1]}::coins::USDC"


def dai():
    return f"{sui_project.TestCoins[-1]}::coins::DAI"


def matic():
    return f"{sui_project.TestCoins[-1]}::coins::MATIC"


def apt():
    return f"{sui_project.TestCoins[-1]}::coins::APT"


def eth():
    return f"{sui_project.TestCoins[-1]}::coins::ETH"


def wbtc():
    return f"{sui_project.TestCoins[-1]}::coins::WBTC"


def bnb():
    return f"{sui_project.TestCoins[-1]}::coins::BNB"


def sui():
    return "0x0000000000000000000000000000000000000000000000000000000000000002::sui::SUI"


def clock():
    return "0x0000000000000000000000000000000000000000000000000000000000000006"


def coin(coin_type):
    return f"0x2::coin::Coin<{coin_type}>"


def balance(coin_type):
    return f"0x2::balance::Supply<{coin_type}>"


def pool(coin_type):
    return f"{sui_project.DolaProtocol[-1]}::dola_pool::Pool<{coin_type}>"


def pool_id(coin_type):
    coin_name = coin_type.split("::")[-1]
    return sui_project.network_config['objects'][f"Pool<{coin_name}>"]


def proposal():
    return f"{sui_project.DolaProtocol[-1]}::governance_v1::Proposal<{sui_project.GenesisProposal[-1]}" \
           f"::genesis_proposal::Certificate>"


def query_portal_relay_event(limit=5):
    dola_protocol = load.dola_protocol_package()
    return dola_protocol.query_events(
        {"MoveEvent": f"{dola_protocol.package_id}::lending_portal::RelayEvent"}, limit=limit)['data']


def query_core_relay_event(limit=5):
    dola_protocol = load.dola_protocol_package()
    return dola_protocol.query_events(
        {"MoveEvent": f"{dola_protocol.package_id}::lending_core_wormhole_adapter::RelayEvent"}, limit=limit)['data']


@functools.lru_cache()
def get_wormhole_adapter_core_emitter() -> List[int]:
    dola_protocol = load.dola_protocol_package()
    result = sui_project.client.sui_getObject(
        dola_protocol.wormhole_adapter_core.CoreState[-1],
        {
            "showType": True,
            "showOwner": True,
            "showPreviousTransaction": False,
            "showDisplay": False,
            "showContent": True,
            "showBcs": False,
            "showStorageRebate": False
        }
    )

    return list(bytes.fromhex(result["data"]["content"]["fields"]["wormhole_emitter"]["fields"]["id"]["id"][2:]))


@functools.lru_cache()
def get_wormhole_adapter_pool_emitter() -> List[int]:
    dola_protocol = load.dola_protocol_package()
    result = sui_project.client.sui_getObject(
        dola_protocol.wormhole_adapter_core.PoolState[-1],
        {
            "showType": True,
            "showOwner": True,
            "showPreviousTransaction": False,
            "showDisplay": False,
            "showContent": True,
            "showBcs": False,
            "showStorageRebate": False
        }
    )

    return list(bytes.fromhex(result["data"]["content"]["fields"]["wormhole_emitter"]["fields"]["id"]["id"][2:]))


def format_emitter_address(addr):
    addr = addr.replace("0x", "")
    if len(addr) < 64:
        addr = "0" * (64 - len(addr)) + addr
    return addr


def register_remote_bridge(wormhole_chain_id, emitter_address):
    genesis_proposal = load.genesis_proposal_package()
    dola_protocol = load.dola_protocol_package()

    emitter_address = format_emitter_address(emitter_address)

    create_proposal()

    basic_params = [
        dola_protocol.governance_v1.GovernanceInfo[-1],  # 0
        sui_project[SuiObject.from_type(proposal())][-1],  # 1
    ]

    bridge_params = [
        sui_project.network_config['objects']['CoreState'],
        wormhole_chain_id,
        list(bytes.fromhex(emitter_address.replace("0x", ""))),
    ]

    sui_project.batch_transaction(
        actual_params=basic_params + bridge_params,
        transactions=[
            [
                genesis_proposal.genesis_proposal.vote_proposal_final,
                [
                    Argument("Input", U16(0)), Argument("Input", U16(1))
                ],
                []
            ],
            [
                genesis_proposal.genesis_proposal.register_remote_bridge,
                [
                    Argument("NestedResult", NestedResult(U16(0), U16(0))),
                    Argument("NestedResult", NestedResult(U16(0), U16(1))),
                    Argument("Input", U16(2)),
                    Argument("Input", U16(3)),
                    Argument("Input", U16(4)),
                ],
                []
            ],
            [
                genesis_proposal.genesis_proposal.destory,
                [
                    Argument("NestedResult", NestedResult(U16(1), U16(0))),
                    Argument("NestedResult", NestedResult(U16(1), U16(1)))
                ],
                []
            ]
        ]
    )


def batch_execute_proposal():
    genesis_proposal = load.genesis_proposal_package()
    dola_protocol = load.dola_protocol_package()

    # Execute genesis proposal

    # Create omnipool params
    decimals = 8

    create_proposal()
    sui_project.batch_transaction(
        actual_params=[dola_protocol.governance_v1.GovernanceInfo[-1],  # 0
                       sui_project[SuiObject.from_type(proposal())][-1],  # 1
                       sui_project.network_config['objects']['WormholeState'],  # 2
                       decimals,  # 3
                       ],
        transactions=[
            [genesis_proposal.genesis_proposal.vote_proposal_final,
             [Argument("Input", U16(0)), Argument("Input", U16(1))],
             []
             ],  # 0. vote_proposal_final
            [genesis_proposal.genesis_proposal.init_wormhole_adapter_core,
             [Argument("NestedResult", NestedResult(U16(0), U16(0))),
              Argument("NestedResult", NestedResult(U16(0), U16(1))),
              Argument("Input", U16(2))],
             []
             ],  # 1. init_wormhole_adapter_core
            [
                genesis_proposal.genesis_proposal.create_omnipool,
                [Argument("NestedResult", NestedResult(U16(1), U16(0))),
                 Argument("NestedResult", NestedResult(U16(1), U16(1))),
                 Argument("Input", U16(3))],
                [wbtc()]
            ],  # 2. create_omnipool btc
            [
                genesis_proposal.genesis_proposal.create_omnipool,
                [Argument("NestedResult", NestedResult(U16(2), U16(0))),
                 Argument("NestedResult", NestedResult(U16(2), U16(1))),
                 Argument("Input", U16(3))],
                [usdt()]
            ],  # 3. create_omnipool usdt
            [
                genesis_proposal.genesis_proposal.create_omnipool,
                [Argument("NestedResult", NestedResult(U16(3), U16(0))),
                 Argument("NestedResult", NestedResult(U16(3), U16(1))),
                 Argument("Input", U16(3))],
                [usdc()]
            ],  # 4. create_omnipool usdc
            [
                genesis_proposal.genesis_proposal.create_omnipool,
                [Argument("NestedResult", NestedResult(U16(4), U16(0))),
                 Argument("NestedResult", NestedResult(U16(4), U16(1))),
                 Argument("Input", U16(3))],
                [sui()]
            ],  # 5. create_omnipool sui
            [genesis_proposal.genesis_proposal.destory,
             [Argument("NestedResult", NestedResult(U16(5), U16(0))),
              Argument("NestedResult", NestedResult(U16(5), U16(1)))],
             []
             ]
        ]
    )
    # Use core state
    init_wormhole_adapter_pool()

    # Init poolmanager params
    # pool_address, dola_chain_id, pool_name, dola_pool_id, pool_weight
    wbtc_pool_params = [list(bytes(wbtc().replace("0x", ""), "ascii")), 0, list(b"WBTC"), 0, 1]
    usdt_pool_params = [list(bytes(usdt().replace("0x", ""), "ascii")), 0, list(b"USDT"), 1, 1]
    usdc_pool_params = [list(bytes(usdc().replace("0x", ""), "ascii")), 0, list(b"USDC"), 2, 1]
    sui_pool_params = [list(bytes(sui().replace("0x", ""), "ascii")), 0, list(b"SUI"), 5, 1]

    create_proposal()

    basic_params = [
        dola_protocol.governance_v1.GovernanceInfo[-1],  # 0
        sui_project[SuiObject.from_type(proposal())][-1],  # 1
        dola_protocol.pool_manager.PoolManagerInfo[-1],  # 2
    ]

    pool_params = wbtc_pool_params + usdt_pool_params + usdc_pool_params + sui_pool_params

    sui_project.batch_transaction(
        actual_params=basic_params + pool_params,
        transactions=[
            [genesis_proposal.genesis_proposal.vote_proposal_final,
             [Argument("Input", U16(0)), Argument("Input", U16(1))],
             []
             ],  # 0. vote_proposal_final
            [
                genesis_proposal.genesis_proposal.register_new_pool,
                [Argument("NestedResult", NestedResult(U16(0), U16(0))),
                 Argument("NestedResult", NestedResult(U16(0), U16(1))),
                 Argument("Input", U16(2)),
                 Argument("Input", U16(3)),
                 Argument("Input", U16(4)),
                 Argument("Input", U16(5)),
                 Argument("Input", U16(6)),
                 Argument("Input", U16(7))],
                []
            ],  # 1. register_new_pool btc
            [
                genesis_proposal.genesis_proposal.register_new_pool,
                [Argument("NestedResult", NestedResult(U16(1), U16(0))),
                 Argument("NestedResult", NestedResult(U16(1), U16(1))),
                 Argument("Input", U16(2)),
                 Argument("Input", U16(8)),
                 Argument("Input", U16(9)),
                 Argument("Input", U16(10)),
                 Argument("Input", U16(11)),
                 Argument("Input", U16(12))],
                []
            ],  # 2. register_new_pool usdt
            [
                genesis_proposal.genesis_proposal.register_new_pool,
                [Argument("NestedResult", NestedResult(U16(2), U16(0))),
                 Argument("NestedResult", NestedResult(U16(2), U16(1))),
                 Argument("Input", U16(2)),
                 Argument("Input", U16(13)),
                 Argument("Input", U16(14)),
                 Argument("Input", U16(15)),
                 Argument("Input", U16(16)),
                 Argument("Input", U16(17))],
                []
            ],  # 3. register_new_pool usdc
            [
                genesis_proposal.genesis_proposal.register_new_pool,
                [Argument("NestedResult", NestedResult(U16(3), U16(0))),
                 Argument("NestedResult", NestedResult(U16(3), U16(1))),
                 Argument("Input", U16(2)),
                 Argument("Input", U16(18)),
                 Argument("Input", U16(19)),
                 Argument("Input", U16(20)),
                 Argument("Input", U16(21)),
                 Argument("Input", U16(22))],
                []
            ],  # 4. register_new_pool sui
            [genesis_proposal.genesis_proposal.destory,
             [Argument("NestedResult", NestedResult(U16(4), U16(0))),
              Argument("NestedResult", NestedResult(U16(4), U16(1)))],
             []
             ]
        ]
    )

    # Init chain group id param
    chain_group_id = 2
    group_chain_ids = [5, 23]

    create_proposal()
    sui_project.batch_transaction(
        actual_params=[dola_protocol.governance_v1.GovernanceInfo[-1],  # 0
                       sui_project[SuiObject.from_type(proposal())][-1],  # 1
                       dola_protocol.app_manager.TotalAppInfo[-1],  # 2
                       dola_protocol.user_manager.UserManagerInfo[-1],  # 3
                       chain_group_id,  # 4
                       group_chain_ids,  # 5
                       ],
        transactions=[
            [genesis_proposal.genesis_proposal.vote_proposal_final,
             [Argument("Input", U16(0)), Argument("Input", U16(1))],
             []
             ],  # 0. vote_proposal_final
            [
                genesis_proposal.genesis_proposal.init_system_core,
                [Argument("NestedResult", NestedResult(U16(0), U16(0))),
                 Argument("NestedResult", NestedResult(U16(0), U16(1))),
                 Argument("Input", U16(2))],
                []
            ],  # 1. init_system_core
            [
                genesis_proposal.genesis_proposal.init_lending_core,
                [Argument("NestedResult", NestedResult(U16(1), U16(0))),
                 Argument("NestedResult", NestedResult(U16(1), U16(1))),
                 Argument("Input", U16(2))],
                []
            ],  # 2. init_lending_core
            [
                genesis_proposal.genesis_proposal.init_chain_group_id,
                [Argument("NestedResult", NestedResult(U16(2), U16(0))),
                 Argument("NestedResult", NestedResult(U16(2), U16(1))),
                 Argument("Input", U16(3)),
                 Argument("Input", U16(4)),
                 Argument("Input", U16(5))],
                []
            ],  # 3. init_chain_group_id
            [genesis_proposal.genesis_proposal.destory,
             [Argument("NestedResult", NestedResult(U16(3), U16(0))),
              Argument("NestedResult", NestedResult(U16(3), U16(1)))],
             []
             ]
        ]
    )

    # Init lending reserve

    # reserve params
    # [dola_pool_id, is_isolated_asset, borrowable_in_isolation, treasury,
    # treasury_factor, borrow_cap_ceiling, collateral_coefficient, borrow_coefficient,
    # base_borrow_rate, borrow_rate_slope1, borrow_rate_slope2, optimal_utilization]
    create_proposal()

    wbtc_reserve_params = [0, False, False, 0,
                           int(0.1 * RAY),
                           0,
                           0,
                           int(0.8 * RAY),
                           int(1.1 * RAY),
                           int(0.02 * RAY),
                           int(0.07 * RAY),
                           int(3 * RAY),
                           int(0.45 * RAY)]
    usdt_reserve_params = [1, False, True, 0,
                           int(0.1 * RAY),
                           0,
                           0,
                           int(0.8 * RAY),
                           int(1.1 * RAY),
                           int(0.02 * RAY),
                           int(0.07 * RAY),
                           int(3 * RAY),
                           int(0.45 * RAY)]
    usdc_reserve_params = [2, False, True, 0,
                           int(0.1 * RAY),
                           0,
                           0,
                           int(0.8 * RAY),
                           int(1.1 * RAY),
                           int(0.02 * RAY),
                           int(0.07 * RAY),
                           int(3 * RAY),
                           int(0.45 * RAY)]
    eth_reserve_params = [3, False, False, 0,
                          int(0.1 * RAY),
                          0,
                          0,
                          int(0.8 * RAY),
                          int(1.1 * RAY),
                          int(0.02 * RAY),
                          int(0.07 * RAY),
                          int(3 * RAY),
                          int(0.45 * RAY)]
    matic_reserve_params = [4, False, False, 0,
                            int(0.1 * RAY),
                            0,
                            0,
                            int(0.8 * RAY),
                            int(1.1 * RAY),
                            int(0.02 * RAY),
                            int(0.07 * RAY),
                            int(3 * RAY),
                            int(0.45 * RAY)]
    sui_reserve_param = [5, True, False, 0,
                         int(0.1 * RAY),
                         0,
                         0,
                         int(0.8 * RAY),
                         int(1.1 * RAY),
                         int(0.02 * RAY),
                         int(0.07 * RAY),
                         int(3 * RAY),
                         int(0.45 * RAY)]

    base_params = [
        dola_protocol.governance_v1.GovernanceInfo[-1],  # 0
        sui_project[SuiObject.from_type(proposal())][-1],  # 1
        dola_protocol.lending_core_storage.Storage[-1],  # 2
        clock()  # 3
    ]
    reserve_params = wbtc_reserve_params + usdt_reserve_params + usdc_reserve_params + eth_reserve_params + matic_reserve_params + sui_reserve_param

    sui_project.batch_transaction(
        actual_params=base_params + reserve_params,
        transactions=[
            [
                genesis_proposal.genesis_proposal.vote_proposal_final,
                [Argument("Input", U16(0)), Argument("Input", U16(1))],
                []
            ],  # 0. vote_proposal_final
            [
                genesis_proposal.genesis_proposal.register_new_reserve,
                [Argument("NestedResult", NestedResult(U16(0), U16(0))),
                 Argument("NestedResult", NestedResult(U16(0), U16(1))),
                 Argument("Input", U16(2)),
                 Argument("Input", U16(3)),
                 Argument("Input", U16(4)),
                 Argument("Input", U16(5)),
                 Argument("Input", U16(6)),
                 Argument("Input", U16(7)),
                 Argument("Input", U16(8)),
                 Argument("Input", U16(9)),
                 Argument("Input", U16(10)),
                 Argument("Input", U16(11)),
                 Argument("Input", U16(12)),
                 Argument("Input", U16(13)),
                 Argument("Input", U16(14)),
                 Argument("Input", U16(15)),
                 Argument("Input", U16(16)),
                 ],
                []
            ],  # 1. register_new_reserve 0 wbtc
            [
                genesis_proposal.genesis_proposal.register_new_reserve,
                [Argument("NestedResult", NestedResult(U16(1), U16(0))),
                 Argument("NestedResult", NestedResult(U16(1), U16(1))),
                 Argument("Input", U16(2)),
                 Argument("Input", U16(3)),
                 Argument("Input", U16(17)),
                 Argument("Input", U16(18)),
                 Argument("Input", U16(19)),
                 Argument("Input", U16(20)),
                 Argument("Input", U16(21)),
                 Argument("Input", U16(22)),
                 Argument("Input", U16(23)),
                 Argument("Input", U16(24)),
                 Argument("Input", U16(25)),
                 Argument("Input", U16(26)),
                 Argument("Input", U16(27)),
                 Argument("Input", U16(28)),
                 Argument("Input", U16(29)),
                 ],
                []
            ],  # 2. register_new_reserve 1 usdt
            [
                genesis_proposal.genesis_proposal.register_new_reserve,
                [Argument("NestedResult", NestedResult(U16(2), U16(0))),
                 Argument("NestedResult", NestedResult(U16(2), U16(1))),
                 Argument("Input", U16(2)),
                 Argument("Input", U16(3)),
                 Argument("Input", U16(30)),
                 Argument("Input", U16(31)),
                 Argument("Input", U16(32)),
                 Argument("Input", U16(33)),
                 Argument("Input", U16(34)),
                 Argument("Input", U16(35)),
                 Argument("Input", U16(36)),
                 Argument("Input", U16(37)),
                 Argument("Input", U16(38)),
                 Argument("Input", U16(39)),
                 Argument("Input", U16(40)),
                 Argument("Input", U16(41)),
                 Argument("Input", U16(42)),
                 ],
                []
            ],  # 3. register_new_reserve 2 usdc
            [
                genesis_proposal.genesis_proposal.register_new_reserve,
                [Argument("NestedResult", NestedResult(U16(3), U16(0))),
                 Argument("NestedResult", NestedResult(U16(3), U16(1))),
                 Argument("Input", U16(2)),
                 Argument("Input", U16(3)),
                 Argument("Input", U16(43)),
                 Argument("Input", U16(44)),
                 Argument("Input", U16(45)),
                 Argument("Input", U16(46)),
                 Argument("Input", U16(47)),
                 Argument("Input", U16(48)),
                 Argument("Input", U16(49)),
                 Argument("Input", U16(50)),
                 Argument("Input", U16(51)),
                 Argument("Input", U16(52)),
                 Argument("Input", U16(53)),
                 Argument("Input", U16(54)),
                 Argument("Input", U16(55)),
                 ],
                []
            ],  # 4. register_new_reserve 3 eth
            [
                genesis_proposal.genesis_proposal.register_new_reserve,
                [Argument("NestedResult", NestedResult(U16(4), U16(0))),
                 Argument("NestedResult", NestedResult(U16(4), U16(1))),
                 Argument("Input", U16(2)),
                 Argument("Input", U16(3)),
                 Argument("Input", U16(56)),
                 Argument("Input", U16(57)),
                 Argument("Input", U16(58)),
                 Argument("Input", U16(59)),
                 Argument("Input", U16(60)),
                 Argument("Input", U16(61)),
                 Argument("Input", U16(62)),
                 Argument("Input", U16(63)),
                 Argument("Input", U16(64)),
                 Argument("Input", U16(65)),
                 Argument("Input", U16(66)),
                 Argument("Input", U16(67)),
                 Argument("Input", U16(68)),
                 ],
                []
            ],  # 5. register_new_reserve 4 matic
            [
                genesis_proposal.genesis_proposal.register_new_reserve,
                [Argument("NestedResult", NestedResult(U16(5), U16(0))),
                 Argument("NestedResult", NestedResult(U16(5), U16(1))),
                 Argument("Input", U16(2)),
                 Argument("Input", U16(3)),
                 Argument("Input", U16(69)),
                 Argument("Input", U16(70)),
                 Argument("Input", U16(71)),
                 Argument("Input", U16(72)),
                 Argument("Input", U16(73)),
                 Argument("Input", U16(74)),
                 Argument("Input", U16(75)),
                 Argument("Input", U16(76)),
                 Argument("Input", U16(77)),
                 Argument("Input", U16(78)),
                 Argument("Input", U16(79)),
                 Argument("Input", U16(80)),
                 Argument("Input", U16(81)),
                 ],
                []
            ],  # 6. register_new_reserve 5 sui
            [
                genesis_proposal.genesis_proposal.destory,
                [Argument("NestedResult", NestedResult(U16(6), U16(0))),
                 Argument("NestedResult", NestedResult(U16(6), U16(1)))],
                []
            ]
        ]
    )


def get_price(symbol):
    pyth_service_url = sui_project.network_config['pyth_service_url']
    feed_id = sui_project.network_config['oracle']['feed_id'][symbol].replace("0x", "")
    url = f"{pyth_service_url}/api/latest_price_feeds?ids[]={feed_id}"
    response = requests.get(url)
    result = response.json()
    price = int(result[0]['ema_price']['price'])
    decimal = int(result[0]['ema_price']['expo']).__abs__()
    return price, decimal


def batch_init_oracle():
    genesis_proposal = load.genesis_proposal_package()
    dola_protocol = load.dola_protocol_package()

    create_proposal()

    # Token price params
    # [dola_pool_id, price, price_decimal]
    (btc_price, btc_price_decimal) = get_price("BTC/USD")
    btc_token_param = [0, btc_price, btc_price_decimal]
    (usdt_price, usdt_price_decimal) = get_price("USDT/USD")
    usdt_token_param = [1, usdt_price, usdt_price_decimal]
    (usdc_price, usdc_price_decimal) = get_price("USDC/USD")
    usdc_token_param = [2, usdc_price, usdc_price_decimal]
    (eth_price, eth_price_decimal) = get_price("ETH/USD")
    eth_token_param = [3, eth_price, eth_price_decimal]
    (matic_price, matic_price_decimal) = get_price("MATIC/USD")
    matic_token_param = [4, matic_price, matic_price_decimal]
    (sui_price, sui_price_decimal) = get_price("SUI/USD")
    sui_token_param = [5, sui_price, sui_price_decimal]

    basic_params = [
        dola_protocol.governance_v1.GovernanceInfo[-1],  # 0
        dola_protocol.oracle.PriceOracle[-1],  # 1
        clock(),  # 2
        sui_project[SuiObject.from_type(proposal())][-1],  # 3
    ]
    token_params = btc_token_param + usdt_token_param + usdc_token_param + eth_token_param + matic_token_param + sui_token_param
    sui_project.batch_transaction(
        actual_params=basic_params + token_params,
        transactions=[
            [
                genesis_proposal.genesis_proposal.vote_proposal_final,
                [Argument("Input", U16(0)), Argument("Input", U16(3))],
                []
            ],
            [
                genesis_proposal.genesis_proposal.register_token_price,
                [
                    Argument("NestedResult", NestedResult(U16(0), U16(0))),
                    Argument("NestedResult", NestedResult(U16(0), U16(1))),
                    Argument("Input", U16(1)),
                    Argument("Input", U16(4)),
                    Argument("Input", U16(5)),
                    Argument("Input", U16(6)),
                    Argument("Input", U16(2))
                ],
                []
            ],
            [
                genesis_proposal.genesis_proposal.register_token_price,
                [
                    Argument("NestedResult", NestedResult(U16(1), U16(0))),
                    Argument("NestedResult", NestedResult(U16(1), U16(1))),
                    Argument("Input", U16(1)),
                    Argument("Input", U16(7)),
                    Argument("Input", U16(8)),
                    Argument("Input", U16(9)),
                    Argument("Input", U16(2))
                ],
                []
            ],
            [
                genesis_proposal.genesis_proposal.register_token_price,
                [
                    Argument("NestedResult", NestedResult(U16(2), U16(0))),
                    Argument("NestedResult", NestedResult(U16(2), U16(1))),
                    Argument("Input", U16(1)),
                    Argument("Input", U16(10)),
                    Argument("Input", U16(11)),
                    Argument("Input", U16(12)),
                    Argument("Input", U16(2))
                ],
                []
            ],
            [
                genesis_proposal.genesis_proposal.register_token_price,
                [
                    Argument("NestedResult", NestedResult(U16(3), U16(0))),
                    Argument("NestedResult", NestedResult(U16(3), U16(1))),
                    Argument("Input", U16(1)),
                    Argument("Input", U16(13)),
                    Argument("Input", U16(14)),
                    Argument("Input", U16(15)),
                    Argument("Input", U16(2))
                ],
                []
            ],
            [
                genesis_proposal.genesis_proposal.register_token_price,
                [
                    Argument("NestedResult", NestedResult(U16(4), U16(0))),
                    Argument("NestedResult", NestedResult(U16(4), U16(1))),
                    Argument("Input", U16(1)),
                    Argument("Input", U16(16)),
                    Argument("Input", U16(17)),
                    Argument("Input", U16(18)),
                    Argument("Input", U16(2))
                ],
                []
            ],
            [
                genesis_proposal.genesis_proposal.register_token_price,
                [
                    Argument("NestedResult", NestedResult(U16(5), U16(0))),
                    Argument("NestedResult", NestedResult(U16(5), U16(1))),
                    Argument("Input", U16(1)),
                    Argument("Input", U16(19)),
                    Argument("Input", U16(20)),
                    Argument("Input", U16(21)),
                    Argument("Input", U16(2))
                ],
                []
            ],
            [
                genesis_proposal.genesis_proposal.destory,
                [Argument("NestedResult", NestedResult(U16(6), U16(0))),
                 Argument("NestedResult", NestedResult(U16(6), U16(1)))],
                []
            ]
        ]
    )


def batch_init():
    active_governance_v1()
    batch_init_oracle()
    batch_execute_proposal()


if __name__ == '__main__':
    batch_init()
