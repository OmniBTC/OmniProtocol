module omnipool::pool {
    use std::ascii;
    use std::type_name;
    use std::vector;

    use serde::serde::{serialize_address, serialize_vector, serialize_u64, deserialize_u64, deserialize_address, vector_slice, serialize_u16, deserialize_u16};
    use serde::u16;
    use sui::balance::{Self, Balance, zero};
    use sui::coin::{Self, Coin};
    use sui::object::{Self, UID};
    use sui::transfer::{Self, share_object};
    use sui::tx_context::{Self, TxContext};

    #[test_only]
    use sui::sui::SUI;
    #[test_only]
    use sui::test_scenario;

    const EINVALID_LENGTH: u64 = 0;

    const EMUST_DEPLOYER: u64 = 0;

    /// The user's information is recorded in the protocol, and the pool only needs to record itself
    struct Pool<phantom CoinType> has key, store {
        id: UID,
        balance: Balance<CoinType>
    }

    /// Give permission to the bridge when Pool is in use
    struct PoolMangerCap has key, store {
        id: UID
    }


    public fun register_cap(ctx: &mut TxContext): PoolMangerCap {
        // todo! consider into govern
        assert!(tx_context::sender(ctx) == @omnipool, EMUST_DEPLOYER);
        PoolMangerCap {
            id: object::new(ctx)
        }
    }

    public fun delete_cap(pool_cap: PoolMangerCap){
        let PoolMangerCap{id} = pool_cap;
        object::delete(id);
    }

    public entry fun create_pool<CoinType>(ctx: &mut TxContext) {
        share_object(Pool<CoinType> {
            id: object::new(ctx),
            balance: zero<CoinType>()
        })
    }

    /// call by user or application
    public entry fun deposit_to<CoinType>(
        pool: &mut Pool<CoinType>,
        deposit_coin: Coin<CoinType>,
        app_payload: vector<u8>,
        ctx: &mut TxContext
    ): vector<u8> {
        let amount = coin::value(&deposit_coin);
        let user = tx_context::sender(ctx);
        let token_name = ascii::into_bytes(type_name::into_string(type_name::get<CoinType>()));
        let pool_payload = encode_deposit_payload(user, amount, token_name, app_payload);
        balance::join(&mut pool.balance, coin::into_balance(deposit_coin));
        pool_payload
    }

    /// call by bridge
    public fun withdraw_to<CoinType>(
        _: &PoolMangerCap,
        pool: &mut Pool<CoinType>,
        pool_payload: vector<u8>,
        ctx: &mut TxContext
    ) {
        let (app_address, amount, _token_name, _app_payload, ) = decode_deposit_payload(pool_payload);
        let balance = balance::split(&mut pool.balance, amount);
        let coin = coin::from_balance(balance, ctx);

        transfer::transfer(coin, app_address);
    }

    /// encode deposit msg
    public fun encode_deposit_payload(
        user: address,
        amount: u64,
        token_name: vector<u8>,
        app_payload: vector<u8>
    ): vector<u8> {
        let pool_payload = vector::empty<u8>();
        serialize_u64(&mut pool_payload, amount);
        serialize_address(&mut pool_payload, user);
        serialize_u16(&mut pool_payload, u16::from_u64(vector::length(&token_name)));
        serialize_vector(&mut pool_payload, token_name);
        if (vector::length(&app_payload) > 0) {
            serialize_u16(&mut pool_payload, u16::from_u64(vector::length(&app_payload)));
            serialize_vector(&mut pool_payload, app_payload);
        };
        pool_payload
    }

    /// decode deposit msg
    public fun decode_deposit_payload(pool_payload: vector<u8>): (address, u64, vector<u8>, vector<u8>) {
        let length = vector::length(&pool_payload);
        let index = 0;
        let data_len;

        data_len = 8;
        let amount = deserialize_u64(&vector_slice(&pool_payload, index, index + data_len));
        index = index + data_len;

        data_len = 20;
        let app_address = deserialize_address(&vector_slice(&pool_payload, index, index + data_len));
        index = index + data_len;

        data_len = 2;
        let token_name_len = u16::to_u64(deserialize_u16(&vector_slice(&pool_payload, index, index + data_len)));
        index = index + data_len;

        data_len = token_name_len;
        let token_name = vector_slice(&pool_payload, index, index + data_len);
        index = index + data_len;

        let app_payload = vector::empty<u8>();
        if (length > index) {
            data_len = 2;
            let app_payload_len = u16::to_u64(deserialize_u16(&vector_slice(&pool_payload, index, index + data_len)));
            index = index + data_len;

            data_len = app_payload_len;
            app_payload = vector_slice(&pool_payload, index, index + data_len);
            index = index + data_len;
        };

        assert!(length == index, EINVALID_LENGTH);

        (app_address, amount, token_name, app_payload)
    }

    #[test]
    public fun test_deposit_to() {
        let manager = @0xA;

        let scenario_val = test_scenario::begin(manager);
        let scenario = &mut scenario_val;
        {
            let ctx = test_scenario::ctx(scenario);
            create_pool<SUI>(ctx);
        };
        test_scenario::next_tx(scenario, manager);
        {
            let pool = test_scenario::take_shared<Pool<SUI>>(scenario);
            assert!(balance::value(&pool.balance) == 0, 0);
            let ctx = test_scenario::ctx(scenario);
            let coin = coin::mint_for_testing<SUI>(100, ctx);
            let app_payload = vector::empty<u8>();
            deposit_to<SUI>(&mut pool, coin, app_payload, ctx);
            assert!(balance::value(&pool.balance) == 100, 0);
            test_scenario::return_shared(pool);
        };
        test_scenario::end(scenario_val);
    }

    #[test]
    public fun test_withdraw_to() {
        let manager = @0x0;
        let user = @0xC;

        let scenario_val = test_scenario::begin(manager);
        let scenario = &mut scenario_val;
        {
            let ctx = test_scenario::ctx(scenario);
            create_pool<SUI>(ctx);
        };
        test_scenario::next_tx(scenario, manager);
        {
            let pool = test_scenario::take_shared<Pool<SUI>>(scenario);
            let manager_cap = register_cap( test_scenario::ctx(scenario));
            let ctx = test_scenario::ctx(scenario);
            let app_payload = vector::empty<u8>();
            let token_name = ascii::into_bytes(type_name::into_string(type_name::get<SUI>()));
            let pool_payload = encode_deposit_payload(user, 100, token_name, app_payload);
            let balance = balance::create_for_testing<SUI>(100);

            balance::join(&mut pool.balance, balance);

            assert!(balance::value(&pool.balance) == 100, 0);

            withdraw_to<SUI>(&manager_cap, &mut pool, pool_payload, ctx);

            assert!(balance::value(&pool.balance) == 0, 0);

            test_scenario::return_shared(pool);
            delete_cap(manager_cap);
        };
        test_scenario::end(scenario_val);
    }
}
