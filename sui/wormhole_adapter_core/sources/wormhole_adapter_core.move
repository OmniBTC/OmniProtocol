// Copyright (c) OmniBTC, Inc.
// SPDX-License-Identifier: Apache-2.0

/// Wormhole bridge adapter, this module is responsible for adapting wormhole to pass messages for settlement center
/// applications (such as lending core). The usage of this module are: 1) Update the status of user_manager and
/// pool_manager; 2) Verify VAA and  message source, decode PoolPaload, and pass it to the correct application
module wormhole_adapter_core::wormhole_adapter_core {
    use app_manager::app_manager::{Self, AppCap};
    use dola_types::types::DolaAddress;
    use governance::genesis::GovernanceCap;
    use wormhole_adapter_core::codec_pool;
    use pool_manager::pool_manager::{PoolManagerCap, Self, PoolManagerInfo};
    use sui::coin::Coin;
    use sui::event;
    use sui::object::{Self, UID};
    use sui::object_table;
    use sui::sui::SUI;
    use sui::table::{Self, Table};
    use sui::transfer;
    use sui::tx_context::TxContext;
    use sui::vec_map::{Self, VecMap};
    use user_manager::user_manager::{Self, UserManagerInfo, UserManagerCap};
    use wormhole::emitter::EmitterCapability;
    use wormhole::external_address::{Self, ExternalAddress};
    use wormhole::state::State as WormholeState;
    use wormhole::wormhole;
    use wormhole_adapter_core::wormhole_adapter_verify::Unit;

    const EMUST_DEPLOYER: u64 = 0;

    const EMUST_SOME: u64 = 1;

    const EINVALID_APP: u64 = 2;

    /// `wormhole_bridge_adapter` adapts to wormhole, enabling cross-chain messaging.
    /// For VAA data, the following validations are required.
    /// For wormhole official library: 1) verify the signature.
    /// For wormhole_bridge_adapter itself: 1) make sure it comes from the correct (emitter_chain, emitter_address) by
    /// VAA; 2) make sure the data has not been processed by VAA hash; 3) make sure the caller is from the correct
    /// application by app_id from pool payload.
    struct CoreState has key, store {
        id: UID,
        // Allow modification of user_manager storage through UserManagerCap
        user_manager_cap: UserManagerCap,
        // Allow modification of pool_manager storage via PoolManagerCap
        pool_manager_cap: PoolManagerCap,
        // Move does not have a contract address, Wormhole uses the emitter
        // in EmitterCapability to represent the send address of this contract
        sender: EmitterCapability,
        // Used to verify that the VAA has been processed
        consumed_vaas: object_table::ObjectTable<vector<u8>, Unit>,
        // Used to verify that (emitter_chain, emitter_address) is correct
        registered_emitters: VecMap<u16, ExternalAddress>,
        // todo! Delete after wormhole running
        cache_vaas: Table<u64, vector<u8>>
    }

    // todo! Delete after wormhole running
    struct VaaEvent has copy, drop {
        vaa: vector<u8>,
        nonce: u64
    }

    /// Initializing the wormhole bridge through governance
    public fun initialize_wormhole_with_governance(
        governance: &GovernanceCap,
        wormhole_state: &mut WormholeState,
        ctx: &mut TxContext
    ) {
        transfer::share_object(
            CoreState {
                id: object::new(ctx),
                user_manager_cap: user_manager::register_cap_with_governance(governance),
                pool_manager_cap: pool_manager::register_cap_with_governance(governance),
                sender: wormhole::register_emitter(wormhole_state, ctx),
                consumed_vaas: object_table::new(ctx),
                registered_emitters: vec_map::empty(),
                cache_vaas: table::new(ctx)
            }
        );
    }

    /// Register the remote bridge through governance
    /// Steps for registering a remote bridge:
    ///  1. Deploy a remote bridge containing (SUI_EMIT_CHAIN, SUI_EMITTER_CHAIN) to represent this contract
    ///  2. By governing the call to `register_remote_bridge`
    public fun register_remote_bridge(
        _: &GovernanceCap,
        core_state: &mut CoreState,
        emitter_chain_id: u16,
        emitter_address: vector<u8>
    ) {
        vec_map::insert(
            &mut core_state.registered_emitters,
            emitter_chain_id,
            external_address::from_bytes(emitter_address)
        );
    }

    /// Only verify that the message is valid, and the message is processed by the corresponding app
    public fun receive_app_message(
        _wormhole_state: &mut WormholeState,
        _core_state: &mut CoreState,
        vaa: vector<u8>,
    ): vector<u8> {
        // let msg = parse_verify_and_replay_protect(
        //     wormhole_state,
        //     &core_state.registered_emitters,
        //     &mut core_state.consumed_vaas,
        //     vaa,
        //     ctx
        // );
        vaa
    }

    public fun receive_deposit(
        _wormhole_state: &mut WormholeState,
        core_state: &mut CoreState,
        app_cap: &AppCap,
        vaa: vector<u8>,
        pool_manager_info: &mut PoolManagerInfo,
        user_manager_info: &mut UserManagerInfo,
        _ctx: &mut TxContext
    ): (DolaAddress, DolaAddress, u256, vector<u8>) {
        // todo: wait for wormhole to go live on the sui testnet and use payload directly for now
        // let vaa = parse_verify_and_replay_protect(
        //     wormhole_state,
        //     &core_state.registered_emitters,
        //     &mut core_state.consumed_vaas,
        //     vaa,
        //     ctx
        // );
        // let (pool, user, amount, dola_pool_id, app_id, app_payload) =
        //     pool::decode_send_deposit_payload(myvaa::get_payload(&vaa));

        let (pool, user, amount, app_id, app_payload) =
            codec_pool::decode_send_deposit_payload(vaa);
        assert!(app_manager::get_app_id(app_cap) == app_id, EINVALID_APP);
        let (actual_amount, _) = pool_manager::add_liquidity(
            &core_state.pool_manager_cap,
            pool_manager_info,
            pool,
            app_manager::get_app_id(app_cap),
            // todo: use wormhole chainid
            (amount as u256),
        );
        if (!user_manager::is_dola_user(user_manager_info, user)) {
            user_manager::register_dola_user_id(&core_state.user_manager_cap, user_manager_info, user);
        };
        // myvaa::destroy(vaa);
        (pool, user, actual_amount, app_payload)
    }

    public fun receive_deposit_and_withdraw(
        _wormhole_state: &mut WormholeState,
        core_state: &mut CoreState,
        app_cap: &AppCap,
        vaa: vector<u8>,
        pool_manager_info: &mut PoolManagerInfo,
        _ctx: &mut TxContext
    ): (DolaAddress, DolaAddress, u256, DolaAddress, u16, vector<u8>) {
        // todo: wait for wormhole to go live on the sui testnet and use payload directly for now
        // let vaa = parse_verify_and_replay_protect(
        //     wormhole_state,
        //     &core_state.registered_emitters,
        //     &mut core_state.consumed_vaas,
        //     vaa,
        //     ctx
        // );
        // let (pool, user, amount, dola_pool_id, app_id, app_payload) =
        //     pool::decode_send_deposit_payload(myvaa::get_payload(&vaa));

        let (deposit_pool, deposit_user, deposit_amount, withdraw_pool, app_id, app_payload) = codec_pool::decode_send_deposit_and_withdraw_payload(
            vaa
        );
        assert!(app_manager::get_app_id(app_cap) == app_id, EINVALID_APP);
        let (actual_amount, _) = pool_manager::add_liquidity(
            &core_state.pool_manager_cap,
            pool_manager_info,
            deposit_pool,
            app_manager::get_app_id(app_cap),
            // todo: use wormhole chainid
            // wormhole_u16::to_u64(myvaa::get_emitter_chain(&vaa)),
            (deposit_amount as u256),
        );
        // myvaa::destroy(vaa);
        (deposit_pool, deposit_user, actual_amount, withdraw_pool, app_id, app_payload)
    }

    public fun receive_withdraw(
        _wormhole_state: &mut WormholeState,
        _core_state: &mut CoreState,
        app_cap: &AppCap,
        vaa: vector<u8>,
        _ctx: &mut TxContext
    ): (DolaAddress, DolaAddress, vector<u8>) {
        // todo: wait for wormhole to go live on the sui testnet and use payload directly for now
        // let vaa = parse_verify_and_replay_protect(
        //     wormhole_state,
        //     &core_state.registered_emitters,
        //     &mut core_state.consumed_vaas,
        //     vaa,
        //     ctx
        // );
        // let (_pool, user, dola_pool_id, app_id, app_payload) =
        //     pool::decode_send_withdraw_payload(myvaa::get_payload(&vaa));
        let (pool, user, app_id, app_payload) =
            codec_pool::decode_send_withdraw_payload(vaa);
        assert!(app_manager::get_app_id(app_cap) == app_id, EINVALID_APP);

        // myvaa::destroy(vaa);
        (pool, user, app_payload)
    }

    public fun remote_register_owner(
        _: &GovernanceCap,
        wormhole_state: &mut WormholeState,
        core_state: &mut CoreState,
        doal_chain_id: u16,
        dola_contract: u256,
        wormhole_message_fee: Coin<SUI>,
    ) {
        let msg = codec_pool::encode_register_owner_payload(
            doal_chain_id,
            dola_contract
        );
        wormhole::publish_message(&mut core_state.sender, wormhole_state, 0, msg, wormhole_message_fee);
        let index = table::length(&core_state.cache_vaas) + 1;
        table::add(&mut core_state.cache_vaas, index, msg);
    }


    public fun remote_register_spender(
        _: &GovernanceCap,
        wormhole_state: &mut WormholeState,
        core_state: &mut CoreState,
        dola_chain_id: u16,
        dola_contract: u256,
        wormhole_message_fee: Coin<SUI>,
    ) {
        let msg = codec_pool::encode_register_spender_payload(
            dola_chain_id,
            dola_contract
        );
        wormhole::publish_message(&mut core_state.sender, wormhole_state, 0, msg, wormhole_message_fee);
        let index = table::length(&core_state.cache_vaas) + 1;
        table::add(&mut core_state.cache_vaas, index, msg);
    }


    public fun remote_delete_owner(
        _: &GovernanceCap,
        wormhole_state: &mut WormholeState,
        core_state: &mut CoreState,
        doal_chain_id: u16,
        dola_contract: u256,
        wormhole_message_fee: Coin<SUI>,
    ) {
        let msg = codec_pool::encode_delete_owner_payload(
            doal_chain_id,
            dola_contract
        );
        wormhole::publish_message(&mut core_state.sender, wormhole_state, 0, msg, wormhole_message_fee);
        let index = table::length(&core_state.cache_vaas) + 1;
        table::add(&mut core_state.cache_vaas, index, msg);
    }

    public fun remote_delete_spender(
        _: &GovernanceCap,
        wormhole_state: &mut WormholeState,
        core_state: &mut CoreState,
        dola_chain_id: u16,
        dola_contract: u256,
        wormhole_message_fee: Coin<SUI>,
    ) {
        let msg = codec_pool::encode_delete_spender_payload(
            dola_chain_id,
            dola_contract
        );
        wormhole::publish_message(&mut core_state.sender, wormhole_state, 0, msg, wormhole_message_fee);
        let index = table::length(&core_state.cache_vaas) + 1;
        table::add(&mut core_state.cache_vaas, index, msg);
    }


    public fun send_withdraw(
        wormhole_state: &mut WormholeState,
        core_state: &mut CoreState,
        app_cap: &AppCap,
        pool_manager_info: &mut PoolManagerInfo,
        pool_address: DolaAddress,
        // todo: fix address
        user: DolaAddress,
        source_chain_id: u16,
        nonce: u64,
        amount: u256,
        wormhole_message_fee: Coin<SUI>,
    ) {
        let (actual_amount, _) = pool_manager::remove_liquidity(
            &core_state.pool_manager_cap,
            pool_manager_info,
            pool_address,
            app_manager::get_app_id(app_cap),
            amount
        );
        let msg = codec_pool::encode_receive_withdraw_payload(
            source_chain_id,
            nonce,
            pool_address,
            user,
            (actual_amount as u64)
        );
        wormhole::publish_message(&mut core_state.sender, wormhole_state, 0, msg, wormhole_message_fee);
        let index = table::length(&core_state.cache_vaas) + 1;
        table::add(&mut core_state.cache_vaas, index, msg);
    }

    public entry fun read_vaa(core_state: &CoreState, index: u64) {
        if (index == 0) {
            index = table::length(&core_state.cache_vaas);
        };
        event::emit(VaaEvent {
            vaa: *table::borrow(&core_state.cache_vaas, index),
            nonce: index
        })
    }
}