module omnipool::pool {
    use std::vector;

    use serde::serde::{serialize_vector, serialize_u64, deserialize_u64, deserialize_address, vector_slice, serialize_u16, deserialize_u16};
    use aptos_framework::coin::{Coin, is_account_registered};
    use std::signer;
    use aptos_framework::account;
    use aptos_framework::account::SignerCapability;
    use aptos_framework::coin;
    use std::hash::sha3_256;
    use aptos_std::type_info;
    use std::string;
    use serde::u16;
    use serde::u16::U16;
    use std::bcs;
    use aptos_framework::aptos_account;
    use aptos_framework::aptos_coin::AptosCoin;

    const SEED: vector<u8> = b"Dola omnipool";

    const EINVALID_LENGTH: u64 = 0;

    const EMUST_DEPLOYER: u64 = 1;

    const EINVALID_TOKEN: u64 = 2;

    const EINVALID_ADMIN: u64 = 3;

    const EMUST_INIT: u64 = 4;

    const ENOT_INIT: u64 = 5;

    const EHAS_POOL: u64 = 6;


    struct PoolManager has key {
        resource_cap: SignerCapability
    }

    /// The user's information is recorded in the protocol, and the pool only needs to record itself
    struct Pool<phantom CoinType> has key, store {
        balance: Coin<CoinType>
    }

    /// Give permission to the bridge when Pool is in use
    struct PoolCap has key, store {}

    /// Make sure the user has aptos coin, and help register if they don't.
    fun transfer<X>(coin_x: Coin<X>, to: address) {
        if (!is_account_registered<X>(to) && type_info::type_of<X>() == type_info::type_of<AptosCoin>()) {
            aptos_account::create_account(to);
        };
        coin::deposit(to, coin_x);
    }

    public fun ensure_admin(sender: &signer): bool {
        signer::address_of(sender) == @omnipool
    }

    public fun ensure_init(): bool {
        exists<PoolManager>(get_resource_address())
    }

    public fun exist_pool<CoinType>(): bool {
        exists<Pool<CoinType>>(get_resource_address())
    }

    public fun register_cap(sender: &signer): PoolCap {
        assert!(ensure_admin(sender), EINVALID_ADMIN);
        // todo! consider into govern
        PoolCap {}
    }

    public fun delete_cap(pool_cap: PoolCap) {
        let PoolCap {} = pool_cap;
    }

    public entry fun init_pool(sender: &signer) {
        assert!(ensure_admin(sender), EINVALID_ADMIN);
        assert!(!ensure_init(), ENOT_INIT);
        let (resource_signer, resource_cap) = account::create_resource_account(sender, SEED);
        move_to(&resource_signer, PoolManager {
            resource_cap
        });
    }

    public fun get_resource_address(): address {
        account::create_resource_address(&@omnipool, SEED)
    }

    public entry fun create_pool<CoinType>(sender: &signer) acquires PoolManager {
        assert!(ensure_admin(sender), EINVALID_ADMIN);
        assert!(ensure_init(), EMUST_INIT);
        assert!(!exist_pool<CoinType>(), EHAS_POOL);
        let resource_cap = &borrow_global<PoolManager>(get_resource_address()).resource_cap;
        move_to(&account::create_signer_with_capability(resource_cap), Pool<CoinType> {
            balance: coin::zero()
        });
    }

    /// call by user or application
    public fun deposit_to<CoinType>(
        sender: &signer,
        deposit_coin: Coin<CoinType>,
        app_id: U16,
        app_payload: vector<u8>,
    ): vector<u8> acquires Pool {
        let amount = coin::value(&deposit_coin);
        let user = signer::address_of(sender);
        let token_name = *string::bytes(&type_info::type_name<CoinType>());
        let pool_address = vector_slice(&sha3_256(token_name), 0, 40);
        let pool_payload = encode_send_deposit_payload(
            pool_address,
            bcs::to_bytes(&user),
            amount,
            token_name,
            app_id,
            app_payload
        );
        let pool = borrow_global_mut<Pool<CoinType>>(get_resource_address());
        coin::merge(&mut pool.balance, deposit_coin);
        pool_payload
    }

    /// call by user or application
    public fun withdraw_to<CoinType>(
        sender: &signer,
        app_id: U16,
        app_payload: vector<u8>,
    ): vector<u8> {
        let user = signer::address_of(sender);
        let token_name = *string::bytes(&type_info::type_name<CoinType>());
        let pool_address = vector_slice(&sha3_256(token_name), 0, 40);
        let pool_payload = encode_send_withdraw_payload(
            pool_address,
            bcs::to_bytes(&user),
            token_name,
            app_id,
            app_payload
        );
        pool_payload
    }

    /// call by bridge
    public fun inner_withdraw<CoinType>(
        _: &PoolCap,
        user: address,
        amount: u64,
        token_name: vector<u8>,
    ) acquires Pool {
        let pool = borrow_global_mut<Pool<CoinType>>(get_resource_address());
        let balance = coin::extract(&mut pool.balance, amount);
        assert!(token_name == *string::bytes(&type_info::type_name<CoinType>()), EINVALID_TOKEN);
        transfer(balance, user);
    }

    public fun deposit_and_withdraw<DepositCoinType, WithdrawCoinType>(
        sender: &signer,
        deposit_coin: Coin<DepositCoinType>,
        withdraw_user: address,
        app_id: U16,
        app_payload: vector<u8>,
    ): vector<u8> acquires Pool {
        let amount = coin::value(&deposit_coin);
        let depoist_user = signer::address_of(sender);
        let deposit_token_name = *string::bytes(&type_info::type_name<DepositCoinType>());
        let deposit_pool_address = vector_slice(&sha3_256(deposit_token_name), 0, 40);

        let pool = borrow_global_mut<Pool<DepositCoinType>>(get_resource_address());
        coin::merge(&mut pool.balance, deposit_coin);

        let withdraw_token_name = *string::bytes(&type_info::type_name<WithdrawCoinType>());
        let withdraw_pool_address = vector_slice(&sha3_256(withdraw_token_name), 0, 40);
        let pool_payload = encode_send_deposit_and_withdraw_payload(
            deposit_pool_address,
            bcs::to_bytes(&depoist_user),
            amount,
            deposit_token_name,
            withdraw_pool_address,
            bcs::to_bytes(&withdraw_user),
            withdraw_token_name,
            app_id,
            app_payload
        );
        pool_payload
    }

    public fun encode_send_deposit_and_withdraw_payload(
        deposit_pool: vector<u8>,
        deposit_user: vector<u8>,
        deposit_amount: u64,
        deposit_token: vector<u8>,
        withdraw_pool: vector<u8>,
        withdraw_user: vector<u8>,
        withdraw_token: vector<u8>,
        app_id: U16,
        app_payload: vector<u8>
    ): vector<u8> {
        let pool_payload = vector::empty<u8>();
        serialize_u16(&mut pool_payload, u16::from_u64(vector::length(&deposit_pool)));
        serialize_vector(&mut pool_payload, deposit_pool);
        serialize_u16(&mut pool_payload, u16::from_u64(vector::length(&deposit_user)));
        serialize_vector(&mut pool_payload, deposit_user);
        serialize_u64(&mut pool_payload, deposit_amount);
        serialize_u16(&mut pool_payload, u16::from_u64(vector::length(&deposit_token)));
        serialize_vector(&mut pool_payload, deposit_token);

        serialize_u16(&mut pool_payload, u16::from_u64(vector::length(&withdraw_pool)));
        serialize_vector(&mut pool_payload, withdraw_pool);

        serialize_u16(&mut pool_payload, u16::from_u64(vector::length(&withdraw_user)));
        serialize_vector(&mut pool_payload, withdraw_user);
        serialize_u16(&mut pool_payload, u16::from_u64(vector::length(&withdraw_token)));
        serialize_vector(&mut pool_payload, withdraw_token);

        serialize_u16(&mut pool_payload, app_id);
        serialize_u16(&mut pool_payload, u16::from_u64(vector::length(&app_payload)));
        serialize_vector(&mut pool_payload, app_payload);
        pool_payload
    }

    /// encode deposit msg
    public fun encode_send_deposit_payload(
        pool: vector<u8>,
        user: vector<u8>,
        amount: u64,
        token_name: vector<u8>,
        app_id: U16,
        app_payload: vector<u8>
    ): vector<u8> {
        let pool_payload = vector::empty<u8>();
        serialize_u16(&mut pool_payload, u16::from_u64(vector::length(&pool)));
        serialize_vector(&mut pool_payload, pool);
        serialize_u16(&mut pool_payload, u16::from_u64(vector::length(&user)));
        serialize_vector(&mut pool_payload, user);
        serialize_u64(&mut pool_payload, amount);
        serialize_u16(&mut pool_payload, u16::from_u64(vector::length(&token_name)));
        serialize_vector(&mut pool_payload, token_name);
        serialize_u16(&mut pool_payload, app_id);
        if (vector::length(&app_payload) > 0) {
            serialize_u16(&mut pool_payload, u16::from_u64(vector::length(&app_payload)));
            serialize_vector(&mut pool_payload, app_payload);
        };
        pool_payload
    }

    /// encode whihdraw msg
    public fun encode_send_withdraw_payload(
        pool: vector<u8>,
        user: vector<u8>,
        token_name: vector<u8>,
        app_id: U16,
        app_payload: vector<u8>
    ): vector<u8> {
        let pool_payload = vector::empty<u8>();
        serialize_u16(&mut pool_payload, u16::from_u64(vector::length(&pool)));
        serialize_vector(&mut pool_payload, pool);
        serialize_u16(&mut pool_payload, u16::from_u64(vector::length(&user)));
        serialize_vector(&mut pool_payload, user);
        serialize_u16(&mut pool_payload, u16::from_u64(vector::length(&token_name)));
        serialize_vector(&mut pool_payload, token_name);
        serialize_u16(&mut pool_payload, app_id);
        if (vector::length(&app_payload) > 0) {
            serialize_u16(&mut pool_payload, u16::from_u64(vector::length(&app_payload)));
            serialize_vector(&mut pool_payload, app_payload);
        };
        pool_payload
    }

    /// encode deposit msg
    public fun encode_receive_withdraw_payload(
        pool: vector<u8>,
        user: vector<u8>,
        amount: u64,
        token_name: vector<u8>
    ): vector<u8> {
        let pool_payload = vector::empty<u8>();
        serialize_u16(&mut pool_payload, u16::from_u64(vector::length(&pool)));
        serialize_vector(&mut pool_payload, pool);
        serialize_u16(&mut pool_payload, u16::from_u64(vector::length(&user)));
        serialize_vector(&mut pool_payload, user);
        serialize_u64(&mut pool_payload, amount);
        serialize_u16(&mut pool_payload, u16::from_u64(vector::length(&token_name)));
        serialize_vector(&mut pool_payload, token_name);
        pool_payload
    }

    /// decode deposit msg
    public fun decode_receive_withdraw_payload(pool_payload: vector<u8>): (address, address, u64, vector<u8>) {
        let length = vector::length(&pool_payload);
        let index = 0;
        let data_len;

        data_len = 20;
        let pool_address = deserialize_address(&vector_slice(&pool_payload, index, index + data_len));
        index = index + data_len;

        data_len = 20;
        let app_address = deserialize_address(&vector_slice(&pool_payload, index, index + data_len));
        index = index + data_len;

        data_len = 8;
        let amount = deserialize_u64(&vector_slice(&pool_payload, index, index + data_len));
        index = index + data_len;

        data_len = 2;
        let token_name_len = deserialize_u16(&vector_slice(&pool_payload, index, index + data_len));
        index = index + data_len;

        data_len = u16::to_u64(token_name_len);
        let token_name = vector_slice(&pool_payload, index, index + data_len);
        index = index + data_len;

        assert!(length == index, EINVALID_LENGTH);

        (pool_address, app_address, amount, token_name)
    }
}