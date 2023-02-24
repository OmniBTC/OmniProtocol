/// Manage the liquidity of all chains' pools
module pool_manager::pool_manager {
    use std::ascii::String;
    use std::option::{Self, Option};
    use std::vector;

    use dola_types::types::{Self, DolaAddress};
    use governance::genesis::GovernanceCap;
    use pool_manager::equilibrium_fee;
    use sui::object::{Self, UID};
    use sui::table::{Self, Table};
    use sui::transfer;
    use sui::tx_context::TxContext;

    #[test_only]
    use std::ascii::string;
    #[test_only]
    use sui::test_scenario;
    #[test_only]
    use governance::genesis;

    /// Equilibrium fees are charged when liquidity is less than 60% of the target liquidity.
    const DEFAULT_ALPHA_1: u256 = 600000000000000000000000000;

    /// Fee ratio 0.5%
    const DEFAULT_LAMBDA_1: u256 = 5000000000000000000000000;

    /// Errors
    const EEXIST_POOL_ID: u64 = 0;
    const ENOT_POOL_ID: u64 = 0;

    const EEXIST_CERTAIN_POOL: u64 = 0;
    const ENOT_CERTAIN_POOL: u64 = 0;

    const EEXIST_POOL_CATALOG: u64 = 0;

    const ENOT_POOL_CATALOG: u64 = 0;

    const ENOT_POOL_INFO: u64 = 0;

    const ENOT_APP_INFO: u64 = 0;

    const EMUST_DEPLOYER: u64 = 0;

    const ENOT_ENOUGH_APP_LIQUIDITY: u64 = 1;

    const ENOT_ENOUGH_POOL_LIQUIDITY: u64 = 1;

    const EONLY_ONE_ADMIN: u64 = 2;

    const EMUST_SOME: u64 = 3;

    const ENONEXISTENT_RESERVE: u64 = 4;

    const ENONEXISTENT_CATALOG: u64 = 5;

    /// Capability allowing liquidity status modification.
    /// Owned by bridge adapters (wormhole, layerzero, etc).
    struct PoolManagerCap has store {}

    /// Responsible for maintaining the global state of different chain pools
    struct PoolManagerInfo has key, store {
        id: UID,
        // dola_pool_id => AppInfo
        app_infos: Table<u16, AppInfo>,
        // dola_pool_id => PoolInfo
        pool_infos: Table<u16, PoolInfo>,
        // pool catalogs
        pool_catalog: PoolCatalog,
    }

    /// Manage App information, including the liquidity that each app has
    struct AppInfo has store {
        // app id => app liquidity
        app_liquidity: Table<u16, Liquidity>
    }

    struct PoolInfo has store {
        // Name for the pool
        name: String,
        // Total liquidity for the pool
        reserve: Liquidity,
        // Current liquidity ratio starts with the boundary value of the
        // charge. Used to evaluate equilibrium fees
        alpha_1: u256,
        // Total weight. Used to evaluate equilibrium fees
        total_weight: u256,
        // Every chain liquidity for the pool
        pools: Table<DolaAddress, PoolLiquidity>,
    }

    struct Liquidity has store {
        value: u256
    }

    struct PoolLiquidity has store {
        // Liquidity of a certain chain pool
        value: u256,
        // The maximum rate of equilibrium fees. Separate settings due to different gas
        // fees for different chains. Used to evaluate equilibrium fees
        lambda_1: u256,
        // The accumulated equilibrium fees of a certain chain pool. The equilibrium fee
        // is kept in the pool manager and is not used
        equilibrium_fee: u256,
        // Weight of a certain chain pool
        weight: u256
    }

    struct PoolCatalog has store {
        // pool address => dola_pool_id
        pool_to_id: Table<DolaAddress, u16>,
        // dola_pool_id => pool addresses
        id_to_pools: Table<u16, vector<DolaAddress>>
    }

    fun init(ctx: &mut TxContext) {
        transfer::share_object(PoolManagerInfo {
            id: object::new(ctx),
            app_infos: table::new(ctx),
            pool_infos: table::new(ctx),
            pool_catalog: PoolCatalog {
                pool_to_id: table::new(ctx),
                id_to_pools: table::new(ctx)
            }
        })
    }

    public fun exist_pool_id(
        pool_manager_info: &PoolManagerInfo,
        dola_pool_id: u16
    ): bool {
        table::contains(&pool_manager_info.pool_infos, dola_pool_id)
    }

    public fun exist_certain_pool(
        pool_manager_info: &PoolManagerInfo,
        pool: DolaAddress
    ): bool {
        let pool_catalog = &pool_manager_info.pool_catalog;
        table::contains(&pool_catalog.pool_to_id, pool)
    }

    /// Giving the bridge adapter the right to make changes to the `pool_manager` module through governance
    public fun register_cap_with_governance(_: &GovernanceCap): PoolManagerCap {
        PoolManagerCap {}
    }

    /// Create a new pool id for managing similar tokens from different chains (e.g. USDC)
    ///
    /// params:
    ///  - `dola_pool_name`: The name of the pool token is valid only for
    /// the name of the first token registered for the token setting.
    ///  - `dola_pool_id`: Represents a class of token in the protocol,
    public fun register_pool_id(
        _: &GovernanceCap,
        pool_manager_info: &mut PoolManagerInfo,
        dola_pool_name: String,
        dola_pool_id: u16,
        ctx: &mut TxContext
    ) {
        assert!(!exist_pool_id(pool_manager_info, dola_pool_id), EEXIST_POOL_ID);

        // Add pool info
        let pool_infos = &mut pool_manager_info.pool_infos;
        let pool_info = PoolInfo {
            name: dola_pool_name,
            reserve: zero_liquidity(),
            pools: table::new(ctx),
            alpha_1: DEFAULT_ALPHA_1,
            total_weight: 0
        };
        table::add(pool_infos, dola_pool_id, pool_info);

        // Add pool catalog
        let pool_catalog = &mut pool_manager_info.pool_catalog;
        table::add(&mut pool_catalog.id_to_pools, dola_pool_id, vector::empty());

        // Add app info
        let app_infos = &mut pool_manager_info.app_infos;
        let app_info = AppInfo {
            app_liquidity: table::new(ctx)
        };
        table::add(app_infos, dola_pool_id, app_info) ;
    }

    /// Add the pool of a certain chain to dola pool id for management
    ///
    /// params:
    ///  - `dola_pool_name`: The name of the pool token is valid only for
    /// the name of the first token registered for the token setting.
    ///  - `dola_pool_id`: Represents a class of token in the protocol,
    /// such as USDT of 1 on all chains.
    ///  - `pool_weight`: By setting the target liquidity ratio of the pool,
    /// the liquidity of the pool can be configured according to the heat of
    /// the chain to prevent the liquidity depletion problem.
    public fun register_pool(
        _: &GovernanceCap,
        pool_manager_info: &mut PoolManagerInfo,
        pool: DolaAddress,
        dola_pool_id: u16
    ) {
        assert!(exist_pool_id(pool_manager_info, dola_pool_id), ENOT_POOL_ID);
        assert!(!exist_certain_pool(pool_manager_info, pool), EEXIST_CERTAIN_POOL);

        // Update pool catalog
        let pool_catalog = &mut pool_manager_info.pool_catalog;
        table::add(&mut pool_catalog.pool_to_id, pool, dola_pool_id);
        let pools = table::borrow_mut(&mut pool_catalog.id_to_pools, dola_pool_id);
        vector::push_back(pools, pool);

        // Update pool info
        let pool_infos = &mut pool_manager_info.pool_infos;
        let pool_info = table::borrow_mut(pool_infos, dola_pool_id);
        table::add(&mut pool_info.pools, pool, PoolLiquidity {
            value: 0,
            lambda_1: DEFAULT_ALPHA_1,
            equilibrium_fee: 0,
            weight: 0
        });
    }

    /// Set the weight of the liquidity pool by governance.
    public fun set_pool_weight(
        _: &GovernanceCap,
        pool_manager_info: &mut PoolManagerInfo,
        pool: DolaAddress,
        weight: u256
    ) {
        assert!(exist_certain_pool(pool_manager_info, pool), ENOT_CERTAIN_POOL);

        let dola_pool_id = get_id_by_pool(pool_manager_info, pool);
        let pool_infos = &mut pool_manager_info.pool_infos;
        let pool_info = table::borrow_mut(pool_infos, dola_pool_id);
        let pool_liquidity = table::borrow_mut(&mut pool_info.pools, pool);
        pool_info.total_weight = pool_info.total_weight - pool_liquidity.weight + weight;
        pool_liquidity.weight = weight;
    }

    /// Set the alpha of equilibrium fee by governance.
    public fun set_equilibrium_alpha(
        _: &GovernanceCap,
        pool_manager_info: &mut PoolManagerInfo,
        dola_pool_id: u16,
        alpha_1: u256
    ) {
        assert!(exist_pool_id(pool_manager_info, dola_pool_id), ENOT_POOL_ID);

        let pool_infos = &mut pool_manager_info.pool_infos;
        let pool_info = table::borrow_mut(pool_infos, dola_pool_id);
        pool_info.alpha_1 = alpha_1;
    }

    /// Set the lambda of equilibrium fee by governance.
    public fun set_equilibrium_lambda(
        _: &GovernanceCap,
        pool_manager_info: &mut PoolManagerInfo,
        pool: DolaAddress,
        lambda_1: u256
    ) {
        assert!(exist_certain_pool(pool_manager_info, pool), ENOT_CERTAIN_POOL);

        let dola_pool_id = get_id_by_pool(pool_manager_info, pool);
        let pool_infos = &mut pool_manager_info.pool_infos;
        let pool_info = table::borrow_mut(pool_infos, dola_pool_id);
        let pool_liquidity = table::borrow_mut(&mut pool_info.pools, pool);
        pool_liquidity.lambda_1 = lambda_1;
    }

    /// Get all DolaAddress according to dola pool id
    public fun get_pools_by_id(pool_manager_info: &mut PoolManagerInfo, dola_pool_id: u16): vector<DolaAddress> {
        assert!(exist_pool_id(pool_manager_info, dola_pool_id), ENOT_POOL_ID);
        let pool_catalog = &mut pool_manager_info.pool_catalog;
        *table::borrow(&mut pool_catalog.id_to_pools, dola_pool_id)
    }

    /// Get pool id according to DolaAddress
    public fun get_id_by_pool(pool_manager_info: &mut PoolManagerInfo, pool: DolaAddress): u16 {
        assert!(exist_certain_pool(pool_manager_info, pool), ENOT_CERTAIN_POOL);
        let pool_catalog = &mut pool_manager_info.pool_catalog;
        assert!(table::contains(&mut pool_catalog.pool_to_id, pool), ENOT_POOL_CATALOG);
        *table::borrow(&mut pool_catalog.pool_to_id, pool)
    }

    /// Get pool name (Such as Btc) according to dola pool id
    public fun get_pool_name_by_id(pool_manager_info: &mut PoolManagerInfo, dola_pool_id: u16): String {
        assert!(exist_pool_id(pool_manager_info, dola_pool_id), ENOT_POOL_ID);
        let pool_infos = &mut pool_manager_info.pool_infos;
        let pool_info = table::borrow(pool_infos, dola_pool_id);
        pool_info.name
    }

    public fun zero_liquidity(): Liquidity {
        Liquidity {
            value: 0
        }
    }

    /// Find DolaAddress according to dola pool id and dst chain
    public fun find_pool_by_chain(
        pool_manager_info: &mut PoolManagerInfo,
        dola_pool_id: u16,
        dst_chain: u16
    ): Option<DolaAddress> {
        let pools = get_pools_by_id(pool_manager_info, dola_pool_id);
        let len = vector::length(&pools);
        let i = 0;
        while (i < len) {
            let d = *vector::borrow(&pools, i);
            if (types::get_dola_chain_id(&d) == dst_chain) {
                return option::some(d)
            };
            i = i + 1;
        };
        option::none()
    }

    /// Get app liquidity for dola pool id
    public fun get_app_liquidity(
        pool_manager_info: &PoolManagerInfo,
        dola_pool_id: u16,
        app_id: u16
    ): u256 {
        assert!(exist_pool_id(pool_manager_info, dola_pool_id), ENOT_POOL_ID);

        let app_infos = &pool_manager_info.app_infos;
        let app_liquidity = &table::borrow(app_infos, dola_pool_id).app_liquidity;
        assert!(table::contains(app_liquidity, app_id), ENOT_APP_INFO);
        table::borrow(app_liquidity, app_id).value
    }

    /// Get all liquidity for dola pool id
    public fun get_token_liquidity(pool_manager_info: &mut PoolManagerInfo, dola_pool_id: u16): u256 {
        assert!(exist_pool_id(pool_manager_info, dola_pool_id), ENOT_POOL_ID);
        let pool_info = table::borrow(&pool_manager_info.pool_infos, dola_pool_id);
        pool_info.reserve.value
    }

    /// Get liquidity for certain pool
    public fun get_pool_liquidity(
        pool_manager_info: &mut PoolManagerInfo,
        pool: DolaAddress,
    ): u256 {
        assert!(exist_certain_pool(pool_manager_info, pool), ENOT_CERTAIN_POOL);
        let dola_pool_id = get_id_by_pool(pool_manager_info, pool);
        let pool_info = table::borrow(&pool_manager_info.pool_infos, dola_pool_id);
        let pool_liquidity = table::borrow(&pool_info.pools, pool);
        pool_liquidity.value
    }

    /// Get equilibrium fee for certain pool
    public fun get_pool_equilibrium_fee(
        pool_manager_info: &mut PoolManagerInfo,
        pool: DolaAddress,
    ): u256 {
        assert!(exist_certain_pool(pool_manager_info, pool), ENOT_CERTAIN_POOL);
        let dola_pool_id = get_id_by_pool(pool_manager_info, pool);
        let pool_info = table::borrow(&pool_manager_info.pool_infos, dola_pool_id);
        let pool_liquidity = table::borrow(&pool_info.pools, pool);
        pool_liquidity.equilibrium_fee
    }

    /// Get total weight for dola pool id
    public fun get_pool_total_weight(
        pool_manager_info: &mut PoolManagerInfo,
        dola_pool_id: u16,
    ): u256 {
        assert!(exist_pool_id(pool_manager_info, dola_pool_id), ENOT_POOL_ID);
        let pool_info = table::borrow(&pool_manager_info.pool_infos, dola_pool_id);
        pool_info.total_weight
    }

    /// Get pool weight for certain pool
    public fun get_pool_weight(
        pool_manager_info: &mut PoolManagerInfo,
        pool: DolaAddress,
    ): u256 {
        assert!(exist_certain_pool(pool_manager_info, pool), ENOT_CERTAIN_POOL);
        let dola_pool_id = get_id_by_pool(pool_manager_info, pool);
        let pool_info = table::borrow(&pool_manager_info.pool_infos, dola_pool_id);
        let pool_liquidity = table::borrow(&pool_info.pools, pool);
        pool_liquidity.weight
    }

    /// Get default alpha_1
    public fun get_default_alpha_1(): u256 {
        DEFAULT_ALPHA_1
    }

    /// Get default lambda 1
    public fun get_default_lambda_1(): u256 {
        DEFAULT_LAMBDA_1
    }

    /// Certain pool has a user deposit operation, update the pool manager status
    public fun add_liquidity(
        _: &PoolManagerCap,
        pool_manager_info: &mut PoolManagerInfo,
        pool: DolaAddress,
        app_id: u16,
        amount: u256
    ): (u256, u256) {
        assert!(exist_certain_pool(pool_manager_info, pool), ENOT_CERTAIN_POOL);
        let dola_pool_id = get_id_by_pool(pool_manager_info, pool);

        // Calculate equilibrium reward
        let pool_infos = &mut pool_manager_info.pool_infos;
        let pool_info = table::borrow_mut(pool_infos, dola_pool_id);
        let pool_liquidity = table::borrow_mut(&mut pool_info.pools, pool);
        let equilibrium_reward = equilibrium_fee::calculate_equilibrium_reward(
            pool_info.reserve.value,
            pool_liquidity.value,
            amount,
            equilibrium_fee::calculate_expected_ratio(pool_info.total_weight, pool_liquidity.weight),
            pool_liquidity.equilibrium_fee,
            pool_liquidity.lambda_1
        );
        let actual_amount = amount + equilibrium_reward;

        // Update liquidity of app infos
        let app_infos = &mut pool_manager_info.app_infos;
        let app_liquidity = &mut table::borrow_mut(app_infos, dola_pool_id).app_liquidity;
        if (!table::contains(app_liquidity, app_id)) {
            table::add(app_liquidity, app_id, Liquidity {
                value: actual_amount
            });
        }else {
            let cur_app_liquidity = table::borrow_mut(app_liquidity, app_id);
            cur_app_liquidity.value = cur_app_liquidity.value + actual_amount
        };

        // Update liquidity of pool infos
        // The pool liquidity store always stores the real number
        pool_info.reserve.value = pool_info.reserve.value + amount;
        pool_liquidity.value = pool_liquidity.value + amount;
        pool_liquidity.equilibrium_fee = pool_liquidity.equilibrium_fee - equilibrium_reward;

        (actual_amount, equilibrium_reward)
    }

    /// Certain pool has a user withdraw operation, update the pool manager status
    public fun remove_liquidity(
        _: &PoolManagerCap,
        pool_manager_info: &mut PoolManagerInfo,
        pool: DolaAddress,
        app_id: u16,
        amount: u256,
    ): (u256, u256) {
        assert!(exist_certain_pool(pool_manager_info, pool), ENOT_CERTAIN_POOL);
        let dola_pool_id = get_id_by_pool(pool_manager_info, pool);

        // Calculate equilibrium fee
        let pool_infos = &mut pool_manager_info.pool_infos;
        let pool_info = table::borrow_mut(pool_infos, dola_pool_id);
        let pool_liquidity = table::borrow_mut(&mut pool_info.pools, pool);
        assert!(pool_liquidity.value >= amount, ENOT_ENOUGH_POOL_LIQUIDITY);
        let equilibrium_fee = equilibrium_fee::calculate_equilibrium_fee(
            pool_info.reserve.value,
            pool_liquidity.value,
            amount,
            equilibrium_fee::calculate_expected_ratio(pool_info.total_weight, pool_liquidity.weight),
            pool_info.alpha_1,
            pool_liquidity.lambda_1
        );
        let actual_amount = amount - equilibrium_fee;

        // Update liquidity of app infos
        let app_infos = &mut pool_manager_info.app_infos;
        let app_liquidity = &mut table::borrow_mut(app_infos, dola_pool_id).app_liquidity;
        assert!(table::contains(app_liquidity, app_id), ENOT_APP_INFO);
        let cur_app_liquidity = table::borrow_mut(app_liquidity, app_id);
        assert!(cur_app_liquidity.value >= amount, ENOT_ENOUGH_APP_LIQUIDITY);
        cur_app_liquidity.value = cur_app_liquidity.value - amount;

        // Update liquidity of pool infos
        // The pool liquidity store always stores the real number
        pool_info.reserve.value = pool_info.reserve.value - actual_amount;
        pool_liquidity.value = pool_liquidity.value - actual_amount;
        pool_liquidity.equilibrium_fee = pool_liquidity.equilibrium_fee + equilibrium_fee;

        (actual_amount, equilibrium_fee)
    }

    /// Destroy manager
    public fun destroy_manager(pool_manager_cap: PoolManagerCap) {
        let PoolManagerCap {} = pool_manager_cap;
    }

    #[test_only]
    public fun init_for_testing(ctx: &mut TxContext) {
        init(ctx)
    }

    #[test_only]
    public fun register_manager_cap_for_testing(): PoolManagerCap {
        PoolManagerCap {}
    }

    #[test]
    public fun test_register_pool() {
        let manager = @pool_manager;

        let scenario_val = test_scenario::begin(manager);
        let scenario = &mut scenario_val;
        {
            init_for_testing(test_scenario::ctx(scenario));
        };
        test_scenario::next_tx(scenario, manager);
        {
            let gonvernance_cap = genesis::register_governance_cap_for_testing();

            let pool_manager_info = test_scenario::take_shared<PoolManagerInfo>(scenario);
            let dola_pool_name = string(b"USDT");
            let pool = types::create_dola_address(0, b"USDT");
            let dola_pool_id = 0;
            register_pool_id(
                &gonvernance_cap,
                &mut pool_manager_info,
                dola_pool_name,
                dola_pool_id,
                test_scenario::ctx(scenario)
            );
            register_pool(&gonvernance_cap, &mut pool_manager_info, pool, dola_pool_id, );
            set_pool_weight(&gonvernance_cap, &mut pool_manager_info, pool, 1, );

            genesis::destroy(gonvernance_cap);

            test_scenario::return_shared(pool_manager_info);
        };
        test_scenario::end(scenario_val);
    }

    #[test]
    public fun test_add_liquidity() {
        let manager = @pool_manager;
        let dola_pool_name = string(b"USDT");
        let pool = types::create_dola_address(0, b"USDT");
        let amount = 100;

        let scenario_val = test_scenario::begin(manager);
        let scenario = &mut scenario_val;
        {
            init_for_testing(test_scenario::ctx(scenario));
        };
        test_scenario::next_tx(scenario, manager);
        {
            let gonvernance_cap = genesis::register_governance_cap_for_testing();

            let pool_manager_info = test_scenario::take_shared<PoolManagerInfo>(scenario);
            let dola_pool_id = 0;
            register_pool_id(
                &gonvernance_cap,
                &mut pool_manager_info,
                dola_pool_name,
                dola_pool_id,
                test_scenario::ctx(scenario)
            );
            register_pool(&gonvernance_cap, &mut pool_manager_info, pool, dola_pool_id, );
            set_pool_weight(&gonvernance_cap, &mut pool_manager_info, pool, 1, );

            genesis::destroy(gonvernance_cap);
            test_scenario::return_shared(pool_manager_info);
        };
        test_scenario::next_tx(scenario, manager);
        {
            let pool_manager_info = test_scenario::take_shared<PoolManagerInfo>(scenario);
            let cap = register_manager_cap_for_testing();
            assert!(get_token_liquidity(&mut pool_manager_info, 0) == 0, 0);
            add_liquidity(
                &cap,
                &mut pool_manager_info,
                pool,
                0,
                amount,
            );
            destroy_manager(cap);

            assert!(get_token_liquidity(&mut pool_manager_info, 0) == amount, 0);
            assert!(get_pool_liquidity(&mut pool_manager_info, pool) == amount, 0);

            test_scenario::return_shared(pool_manager_info);
        };

        test_scenario::end(scenario_val);
    }

    #[test]
    public fun test_remove_liquidity() {
        let manager = @pool_manager;
        let dola_pool_name = string(b"USDT");
        let pool = types::create_dola_address(0, b"USDT");
        let amount = 100;

        let scenario_val = test_scenario::begin(manager);
        let scenario = &mut scenario_val;
        {
            init_for_testing(test_scenario::ctx(scenario));
        };
        test_scenario::next_tx(scenario, manager);
        {
            let gonvernance_cap = genesis::register_governance_cap_for_testing();

            let pool_manager_info = test_scenario::take_shared<PoolManagerInfo>(scenario);

            let dola_pool_id = 0;
            register_pool_id(
                &gonvernance_cap,
                &mut pool_manager_info,
                dola_pool_name,
                dola_pool_id,
                test_scenario::ctx(scenario)
            );
            register_pool(&gonvernance_cap, &mut pool_manager_info, pool, dola_pool_id, );
            set_pool_weight(&gonvernance_cap, &mut pool_manager_info, pool, 1, );

            genesis::destroy(gonvernance_cap);

            test_scenario::return_shared(pool_manager_info);
        };
        test_scenario::next_tx(scenario, manager);
        {
            let pool_manager_info = test_scenario::take_shared<PoolManagerInfo>(scenario);
            let cap = register_manager_cap_for_testing();
            add_liquidity(
                &cap,
                &mut pool_manager_info,
                pool,
                0,
                amount,
            );
            destroy_manager(cap);

            test_scenario::return_shared(pool_manager_info);
        };
        test_scenario::next_tx(scenario, manager);
        {
            let pool_manager_info = test_scenario::take_shared<PoolManagerInfo>(scenario);
            let cap = register_manager_cap_for_testing();

            assert!(get_token_liquidity(&mut pool_manager_info, 0) == amount, 0);
            assert!(get_pool_liquidity(&mut pool_manager_info, pool) == amount, 0);

            remove_liquidity(
                &cap,
                &mut pool_manager_info,
                pool,
                0,
                amount
            );
            destroy_manager(cap);

            assert!(get_token_liquidity(&mut pool_manager_info, 0) == 0, 0);
            assert!(get_pool_liquidity(&mut pool_manager_info, pool) == 0, 0);

            test_scenario::return_shared(pool_manager_info);
        };
        test_scenario::end(scenario_val);
    }
}
