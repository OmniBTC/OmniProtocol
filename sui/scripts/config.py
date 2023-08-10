# Some constants for the scripts

# dola reserves count
DOLA_RESERVES_COUNT = 8

# dola protocol decimal
DOLA_DECIMAL = 8

# eth zero address
ETH_ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

# eth decimal
ETH_DECIMAL = 18

# eth gas unit
G_WEI = 10 ** 9

# active relayer num
ACTIVE_RELAYER_NUM = 4

# network name -> wormhole chain id
NET_TO_WORMHOLE_CHAIN_ID = {
    # mainnet
    "mainnet": 2,
    "bsc-main": 4,
    "polygon-main": 5,
    "avax-main": 6,
    "optimism-main": 24,
    "arbitrum-main": 23,
    "aptos-mainnet": 22,
    "sui-mainnet": 21,
    # testnet
    "goerli": 2,
    "bsc-test": 4,
    "polygon-test": 5,
    "avax-test": 6,
    "optimism-test": 24,
    "arbitrum-test": 23,
    "aptos-testnet": 22,
    "sui-testnet": 21,
}

# network name -> dola chain id
NET_TO_DOLA_CHAIN_ID = {
    # mainnet
    "sui-mainnet": 0,
    "polygon-main": 5,
    "arbitrum-main": 23,
    "optimism-main": 24,
}

# network name -> wormhole emitter
NET_TO_WORMHOLE_EMITTER = {
    # mainnet
    "optimism-main": "0x94650D61b940496b1BD88767b7B541b1121e0cCF",
    "arbitrum-main": "0x098D26E4d2E98C1Dde14C543Eb6804Fd98Af9CB4",
    "polygon-main": "0x4445c48e9B70F78506E886880a9e09B501ED1E13",
    "sui-mainnet": "0xabbce6c0c2c7cd213f4c69f8a685f6dfc1848b6e3f31dd15872f4e777d5b3e86",
    "sui-mainnet-pool": "0xdd1ca0bd0b9e449ff55259e5bcf7e0fc1b8b7ab49aabad218681ccce7b202bd6",
    # testnet
    "polygon-test": "0x83B787B99B1f5E9D90eDcf7C09E41A5b336939A7",
    "avax-test": "0xF3d8cFbEee2A16c47b8f5f05f6452Bf38b0346Ec",
    "sui-testnet": "0x4f9f241cd3a249e0ef3d9ece8b1cd464c38c95d6d65c11a2ddd5645632e6e8a0",
    "sui-testnet-pool": "0xf737cbc8e158b1b76b1f161f048e127ae4560a90df1c96002417802d7d23fe3f",
}

# native token name -> symbol
NATIVE_TOKEN_NAME_TO_KUCOIN_SYMBOL = {
    "eth": "ETH/USDT",
    "avax": "AVAX/USDT",
    "matic": "MATIC/USDT",
    "bnb": "BNB/USDT",
    "sui": "SUI/USDT",
    "apt": "APT/USDT"
}

# native token name -> decimal
NATIVE_TOKEN_NAME_TO_DECIMAL = {
    "eth": 18,
    "avax": 18,
    "matic": 18,
    "bnb": 18,
    "sui": 9,
    "apt": 8
}

# call type -> call_name
CALL_TYPE_TO_CALL_NAME = {
    0: {
        0: "binding",
        1: "unbinding",
    },
    1: {
        0: "supply",
        1: "withdraw",
        2: "borrow",
        3: "repay",
        4: "liquidate",
        5: "as_collateral",
        6: "cancel_as_collateral",
    }
}

# dola_chain_id -> network
# mainnet
DOLA_CHAIN_ID_TO_NETWORK = {
    0: "sui-mainnet",
    5: "polygon-main",
    6: "avax-main",
    23: "arbitrum-main",
    24: "optimism-main",
}
# testnet
# DOLA_CHAIN_ID_TO_NETWORK = {
#     0: "sui-testnet",
#     5: "polygon-test",
#     6: "avax-test",
#     23: "arbitrum-test",
#     24: "optimism-test",
# }

# network -> native token
# mainnet
NETWORK_TO_NATIVE_TOKEN = {
    "sui-mainnet": "sui",
    "polygon-main": "matic",
    "avax-main": "avax",
    "arbitrum-main": "eth",
    "optimism-main": "eth",
}

# sui token -> sui pool
# mainnet
SUI_TOKEN_TO_POOL = {
    "0x0000000000000000000000000000000000000000000000000000000000000002::sui::SUI": "0x19b5315353192fcbe21214d51520b1292cd78215849cd5a9a9ea80ee3916cb73"
}

#  testnet
# SUI_TOKEN_TO_POOL = {
#     "0x0000000000000000000000000000000000000000000000000000000000000002::sui::SUI": "0x283f712a6c6a9361132e2d75aee4b4499f98892a3b8cfd4a7244ad6862c62aa9"
# }
