from pathlib import Path

import sui_brownie
from dola_sui_sdk import DOLA_CONFIG

net = "sui-testnet"

sui_project = sui_brownie.SuiProject(project_path=DOLA_CONFIG["DOLA_SUI_PATH"], network=net)
sui_project.active_account("Relayer")

serde_package = sui_brownie.SuiPackage(
    package_path=DOLA_CONFIG["DOLA_SUI_PATH"].joinpath("serde")
)

serde_package.publish_package()

dola_types_package = sui_brownie.SuiPackage(
    package_path=DOLA_CONFIG["DOLA_SUI_PATH"].joinpath("dola_types")
)

dola_types_package.publish_package(
    replace_address=dict(serde=serde_package.package_id
                         ))

ray_math_package = sui_brownie.SuiPackage(
    package_path=DOLA_CONFIG["DOLA_SUI_PATH"].joinpath("ray_math")
)

ray_math_package.publish_package()

governance_package = sui_brownie.SuiPackage(
    package_path=DOLA_CONFIG["DOLA_SUI_PATH"].joinpath("governance")
)

governance_package.publish_package(
    replace_address=dict(serde=serde_package.package_id))

user_manager_package = sui_brownie.SuiPackage(
    package_path=DOLA_CONFIG["DOLA_SUI_PATH"].joinpath("user_manager")
)

user_manager_package.publish_package(
    replace_address=dict(serde=serde_package.package_id,
                         dola_types=dola_types_package.package_id,
                         governance=governance_package.package_id))

app_manager_package = sui_brownie.SuiPackage(
    package_path=DOLA_CONFIG["DOLA_SUI_PATH"].joinpath("app_manager")
)

app_manager_package.publish_package(
    replace_address=dict(serde=serde_package.package_id,
                         governance=governance_package.package_id))

oracle_package = sui_brownie.SuiPackage(
    package_path=DOLA_CONFIG["DOLA_SUI_PATH"].joinpath("oracle")
)

oracle_package.publish_package()

pool_manager_package = sui_brownie.SuiPackage(
    package_path=DOLA_CONFIG["DOLA_SUI_PATH"].joinpath("pool_manager")
)

pool_manager_package.publish_package(
    replace_address=dict(serde=serde_package.package_id, governance=governance_package.package_id,
                         dola_types=dola_types_package.package_id, ray_math=ray_math_package.package_id))

wormhole_package = sui_brownie.SuiPackage(
    package_path=Path.home().joinpath(Path(
        ".move/https___github_com_OmniBTC_wormhole_git_dcceff545df0d9dd7ce537f51373d3cc6d20d00d/sui/wormhole")),
)

wormhole_package.publish_package()

omnipool_package = sui_brownie.SuiPackage(
    package_path=DOLA_CONFIG["DOLA_SUI_PATH"].joinpath("omnipool")
)

omnipool_package.publish_package(replace_address=dict(
    serde=serde_package.package_id,
    dola_types=dola_types_package.package_id,
    wormhole=wormhole_package.package_id
))

wormhole_adapter_core_package = sui_brownie.SuiPackage(
    package_path=DOLA_CONFIG["DOLA_SUI_PATH"].joinpath("wormhole_adapter_core")
)

wormhole_adapter_core_package.publish_package(replace_address=dict(
    wormhole_adapter_core="0x0",
    serde=serde_package.package_id,
    dola_types=dola_types_package.package_id,
    wormhole=wormhole_package.package_id,
    governance=governance_package.package_id,
    app_manager=app_manager_package.package_id,
    pool_manager=pool_manager_package.package_id,
    user_manager=user_manager_package.package_id
))

lending_core_package = sui_brownie.SuiPackage(
    package_path=DOLA_CONFIG["DOLA_SUI_PATH"].joinpath("lending_core")
)

lending_core_package.publish_package(replace_address=dict(
    lending_core="0x0",
    serde=serde_package.package_id,
    dola_types=dola_types_package.package_id,
    ray_math=ray_math_package.package_id,
    oracle=oracle_package.package_id,
    app_manager=app_manager_package.package_id,
    pool_manager=pool_manager_package.package_id,
    user_manager=user_manager_package.package_id,
    wormhole=wormhole_package.package_id,
    wormhole_adapter_core=wormhole_adapter_core_package.package_id,
    governance=governance_package.package_id
))

system_core_package = sui_brownie.SuiPackage(
    package_path=DOLA_CONFIG["DOLA_SUI_PATH"].joinpath("system_core")
)

system_core_package.publish_package(replace_address=dict(
    serde=serde_package.package_id,
    dola_types=dola_types_package.package_id,
    app_manager=app_manager_package.package_id,
    user_manager=user_manager_package.package_id,
    wormhole=wormhole_package.package_id,
    wormhole_adapter_core=wormhole_adapter_core_package.package_id,
    governance=governance_package.package_id
))

dola_portal_package = sui_brownie.SuiPackage(
    package_path=DOLA_CONFIG["DOLA_SUI_PATH"].joinpath("dola_portal")
)

dola_portal_package.publish_package(replace_address=dict(
    serde=serde_package.package_id,
    dola_types=dola_types_package.package_id,
    pool_manager=pool_manager_package.package_id,
    user_manager=user_manager_package.package_id,
    app_manager=app_manager_package.package_id,
    lending_core=lending_core_package.package_id,
    system_core=system_core_package.package_id,
    oracle=oracle_package.package_id,
    wormhole_adapter_core=wormhole_adapter_core_package.package_id,
    wormhole=wormhole_package.package_id,
    omnipool=omnipool_package.package_id,
    governance=governance_package.package_id
))

external_interfaces_package = sui_brownie.SuiPackage(
    package_path=DOLA_CONFIG["DOLA_SUI_PATH"].joinpath("external_interfaces")
)

external_interfaces_package.publish_package(replace_address=dict(
    pool_manager=pool_manager_package.package_id,
    user_manager=user_manager_package.package_id,
    dola_types=dola_types_package.package_id,
    lending_core=lending_core_package.package_id,
    ray_math=ray_math_package.package_id,
    oracle=oracle_package.package_id
))

genesis_proposal_package = sui_brownie.SuiPackage(
    package_path=DOLA_CONFIG["DOLA_SUI_PATH"].joinpath(
        "proposals/genesis_proposal")
)

genesis_proposal_package.publish_package(replace_address=dict(
    pool_manager=pool_manager_package.package_id,
    user_manager=user_manager_package.package_id,
    wormhole=wormhole_package.package_id,
    wormhole_adapter_core=wormhole_adapter_core_package.package_id,
    governance=governance_package.package_id,
    lending_core=lending_core_package.package_id,
    system_core=system_core_package.package_id,
    dola_portal=dola_portal_package.package_id,
    app_manager=app_manager_package.package_id,
    dola_types=dola_types_package.package_id,
    oracle=oracle_package.package_id,
    omnipool=omnipool_package.package_id
))

test_coins_package = sui_brownie.SuiPackage(
    package_path=DOLA_CONFIG["DOLA_SUI_PATH"].joinpath("test_coins")
)

test_coins_package.publish_package()

print("---------------------------Deployed Package ID-------------------------------------\n")
print(f"serde={serde_package.package_id}")
print(f"dola_types={dola_types_package.package_id}")
print(f"ray_math={ray_math_package.package_id}")
print(f"omnipool={omnipool_package.package_id}")
print(f"app_manager={app_manager_package.package_id}")
print(f"governance={governance_package.package_id}")
print(f"oracle={oracle_package.package_id}")
print(f"pool_manager={pool_manager_package.package_id}")
print(f"wormhole={wormhole_package.package_id}")
print(f"wormhole_adapter_core={wormhole_adapter_core_package.package_id}")
print(f"lending_core={lending_core_package.package_id}")
print(f"system_core={system_core_package.package_id}")
print(f"dola_portal={dola_portal_package.package_id}")
print(f"external_interfaces={external_interfaces_package.package_id}")
print(f"genesis_proposal={genesis_proposal_package.package_id}")
print(f"test_coins={test_coins_package.package_id}")
