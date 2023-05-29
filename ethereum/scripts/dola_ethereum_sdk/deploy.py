import yaml
from brownie import network

from dola_ethereum_sdk import DOLA_CONFIG, get_account, set_ethereum_network, config


def deploy():
    account = get_account()
    cur_net = network.show_active()
    print(f"Current network:{cur_net}, account:{account}")

    wormhole_address = config["networks"][cur_net]["wormhole"]
    wormhole_chainid = config["networks"][cur_net]["wormhole_chainid"]
    wormhole_finality = config["networks"][cur_net]["wormhole_finality"]
    core_emitter = config["networks"][cur_net]["core_emitter"]

    # DOLA_CONFIG["DOLA_ETHEREUM_PROJECT"]["LibAsset"].deploy({'from': account})

    # print("deploy wormhole adapter pool...")
    # wormhole_adapter_pool = DOLA_CONFIG["DOLA_ETHEREUM_PROJECT"]["WormholeAdapterPool"].deploy(
    #     wormhole_address,
    #     wormhole_chainid,
    #     wormhole_finality,
    #     21,
    #     core_emitter,
    #     {'from': account}
    # )
    #
    # print("deploy lending portal...")
    # lending_portal = DOLA_CONFIG["DOLA_ETHEREUM_PROJECT"]["LendingPortal"].deploy(
    #     wormhole_adapter_pool.address,
    #     {'from': account}
    # )

    print("deploy system portal...")
    system_portal = DOLA_CONFIG["DOLA_ETHEREUM_PROJECT"]["SystemPortal"].deploy(
        "0x1FFBE74B4665037070E734daf9F79fa33B6d54a8",
        {'from': account}
    )

    path = DOLA_CONFIG["DOLA_PROJECT_PATH"].joinpath('ethereum/brownie-config.yaml')
    with open(path, "r") as f:
        config_file = yaml.safe_load(f)

    config_file["networks"][cur_net]["wormhole_adapter_pool"] = wormhole_adapter_pool.address
    config_file["networks"][cur_net]["lending_portal"] = lending_portal.address
    config_file["networks"][cur_net]["system_portal"] = system_portal.address

    if "test" in cur_net:
        wbtc = deploy_token("WBTC")

        usdt = deploy_token("USDT")

        usdc = deploy_token("USDC")

        config_file["networks"][cur_net]["wbtc"] = wbtc.address
        config_file["networks"][cur_net]["usdt"] = usdt.address
        config_file["networks"][cur_net]["usdc"] = usdc.address

    with open(path, "w") as f:
        yaml.safe_dump(config_file, f)


def deploy_token(token_name="USDT"):
    account = get_account()

    print(f"deploy test token {token_name}...")
    return DOLA_CONFIG["DOLA_ETHEREUM_PROJECT"]["MockToken"].deploy(
        token_name, token_name, {'from': account}
    )


if __name__ == "__main__":
    set_ethereum_network("polygon-main")
    deploy()
