from pathlib import Path

import sui_brownie

serde_package = sui_brownie.SuiPackage(
    brownie_config=Path("../../"),
    network="sui-devnet",
    is_compile=True,
    package_id=None,
    package_path="../../serde"
)

serde_package.publish_package()

omnipool_package = sui_brownie.SuiPackage(
    brownie_config=Path("../../"),
    network="sui-devnet",
    is_compile=True,
    package_id=None,
    package_path="../../omnipool"
)

omnipool_package.publish_package(replace_address=dict(serde=serde_package.package_id))

governance_package = sui_brownie.SuiPackage(
    brownie_config=Path("../../"),
    network="sui-devnet",
    is_compile=True,
    package_id=None,
    package_path="../../omnicore/governance"
)

governance_package.publish_package(replace_address=dict(serde=serde_package.package_id))

app_manager_package = sui_brownie.SuiPackage(
    brownie_config=Path("../../"),
    network="sui-devnet",
    is_compile=True,
    package_id=None,
    package_path="../../omnicore/app_manager"
)

app_manager_package.publish_package(
    replace_address=dict(serde=serde_package.package_id, governance=governance_package.package_id))

oracle_package = sui_brownie.SuiPackage(
    brownie_config=Path("../../"),
    network="sui-devnet",
    is_compile=True,
    package_id=None,
    package_path="../../omnicore/oracle"
)

oracle_package.publish_package()

pool_manager_package = sui_brownie.SuiPackage(
    brownie_config=Path("../../"),
    network="sui-devnet",
    is_compile=True,
    package_id=None,
    package_path="../../omnicore/pool_manager"
)

pool_manager_package.publish_package(
    replace_address=dict(serde=serde_package.package_id, governance=governance_package.package_id))

wormhole_package = sui_brownie.SuiPackage(
    brownie_config=Path("../../"),
    network="sui-devnet",
    is_compile=True,
    package_id=None,
    package_path=Path.home().joinpath(Path(
        ".move/https___github_com_OmniBTC_wormhole_git_3b20c0a0966dd5c936c9584b12dcf3b6ccc956e9/sui/wormhole")),
)

wormhole_package.publish_package()

wormhole_bridge_package = sui_brownie.SuiPackage(
    brownie_config=Path("../../"),
    network="sui-devnet",
    is_compile=True,
    package_id=None,
    package_path="../../wormhole_bridge"
)

wormhole_bridge_package.publish_package(replace_address=dict(
    serde=serde_package.package_id,
    wormhole=wormhole_package.package_id,
    omnipool=omnipool_package.package_id,
    app_manager=app_manager_package.package_id,
    pool_manager=pool_manager_package.package_id
))

lending_package = sui_brownie.SuiPackage(
    brownie_config=Path("../../"),
    network="sui-devnet",
    is_compile=True,
    package_id=None,
    package_path="../../omnicore/lending"
)

lending_package.publish_package(replace_address=dict(
    serde=serde_package.package_id,
    oracle=oracle_package.package_id,
    app_manager=app_manager_package.package_id,
    pool_manager=pool_manager_package.package_id,
    wormhole=wormhole_package.package_id,
    wormhole_bridge=wormhole_bridge_package.package_id,
    governance=governance_package.package_id
))

lending_portal_package = sui_brownie.SuiPackage(
    brownie_config=Path("../../"),
    network="sui-devnet",
    is_compile=True,
    package_id=None,
    package_path="../../lending_portal"
)

lending_portal_package.publish_package(replace_address=dict(
    serde=serde_package.package_id,
    wormhole_bridge=wormhole_bridge_package.package_id,
    wormhole=wormhole_package.package_id,
    omnipool=omnipool_package.package_id
))

example_proposal_package = sui_brownie.SuiPackage(
    brownie_config=Path("../../"),
    network="sui-devnet",
    is_compile=True,
    package_id=None,
    package_path="../../omnicore/example_proposal"
)

example_proposal_package.publish_package(replace_address=dict(
    pool_manager=pool_manager_package.package_id,
    wormhole_bridge=wormhole_bridge_package.package_id,
    governance=governance_package.package_id,
    lending=lending_package.package_id,
    app_manager=app_manager_package.package_id
))

test_coins_package = sui_brownie.SuiPackage(
    brownie_config=Path("../../"),
    network="sui-devnet",
    is_compile=True,
    package_id=None,
    package_path="../../test_coins"
)

test_coins_package.publish_package()

print("---------------------------Deployed Package ID-------------------------------------\n")
print(f"serde={serde_package.package_id}")
print(f"omnipool={omnipool_package.package_id}")
print(f"app_manager={app_manager_package.package_id}")
print(f"governance={governance_package.package_id}")
print(f"oracle={oracle_package.package_id}")
print(f"pool_manager={pool_manager_package.package_id}")
print(f"wormhole={wormhole_package.package_id}")
print(f"wormhole_bridge={wormhole_bridge_package.package_id}")
print(f"lending={lending_package.package_id}")
print(f"lending_portal={lending_portal_package.package_id}")
print(f"example_proposal={example_proposal_package.package_id}")
print(f"test_coins={test_coins_package.package_id}")
