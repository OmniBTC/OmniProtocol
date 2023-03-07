module lending_core::codec_lending {

    use dola_types::dola_address::{Self, DolaAddress};
    use std::vector;
    use serde::serde;

    /// Errors
    /// Invalid length of Payload
    const EINVALID_LENGTH: u64 = 0;

    /// Wrong call type
    const EINVALID_CALL_TYPE: u64 = 1;

    /// Lending call type

    const SUPPLY: u8 = 0;

    const WITHDRAW: u8 = 1;

    const BORROW: u8 = 2;

    const REPAY: u8 = 3;

    const LIQUIDATE: u8 = 4;

    const AS_COLLATERAL: u8 = 5;

    const CANCLE_AS_COLLATERAL: u8 = 6;

    /// Getter

    public fun get_supply_type(): u8 {
        SUPPLY
    }

    public fun get_withdraw_type(): u8 {
        WITHDRAW
    }

    public fun get_borrow_type(): u8 {
        BORROW
    }

    public fun get_repay_type(): u8 {
        REPAY
    }

    public fun get_as_colleteral_type(): u8 {
        AS_COLLATERAL
    }

    public fun get_cancel_as_colleteral_type(): u8 {
        CANCLE_AS_COLLATERAL
    }


    /// Encode and decode

    /// Encode supply or repay
    public fun encode_deposit_payload(
        source_chain_id: u16,
        nonce: u64,
        receiver: DolaAddress,
        lending_call_type: u8
    ): vector<u8> {
        let payload = vector::empty<u8>();

        serde::serialize_u16(&mut payload, source_chain_id);
        serde::serialize_u64(&mut payload, nonce);

        let receiver = dola_address::encode_dola_address(receiver);
        serde::serialize_u16(&mut payload, (vector::length(&receiver) as u16));
        serde::serialize_vector(&mut payload, receiver);
        serde::serialize_u8(&mut payload, lending_call_type);
        payload
    }

    /// Decode supply or repay
    public fun decode_deposit_payload(app_payload: vector<u8>): (u16, u64, DolaAddress, u8) {
        let index = 0;
        let data_len;

        data_len = 2;
        let source_chain_id = serde::deserialize_u16(&serde::vector_slice(&app_payload, index, index + data_len));
        index = index + data_len;

        data_len = 8;
        let nonce = serde::deserialize_u64(&serde::vector_slice(&app_payload, index, index + data_len));
        index = index + data_len;

        data_len = 2;
        let receive_length = serde::deserialize_u16(&serde::vector_slice(&app_payload, index, index + data_len));
        index = index + data_len;

        data_len = (receive_length as u64);
        let receiver = dola_address::decode_dola_address(serde::vector_slice(&app_payload, index, index + data_len));
        index = index + data_len;

        data_len = 1;
        let lending_call_type = serde::deserialize_u8(&serde::vector_slice(&app_payload, index, index + data_len));
        index = index + data_len;

        assert!(index == vector::length(&app_payload), EINVALID_LENGTH);

        (source_chain_id, nonce, receiver, lending_call_type)
    }

    /// Encode withdraw or borrow
    public fun encode_withdraw_payload(
        source_chain_id: u16,
        nonce: u64,
        amount: u64,
        pool_address: DolaAddress,
        receiver: DolaAddress,
    ): vector<u8> {
        let payload = vector::empty<u8>();

        serde::serialize_u16(&mut payload, source_chain_id);
        serde::serialize_u64(&mut payload, nonce);
        serde::serialize_u64(&mut payload, amount);

        let pool_address = dola_address::encode_dola_address(pool_address);
        serde::serialize_u16(&mut payload, (vector::length(&pool_address) as u16));
        serde::serialize_vector(&mut payload, pool_address);

        let receiver = dola_address::encode_dola_address(receiver);
        serde::serialize_u16(&mut payload, (vector::length(&receiver) as u16));
        serde::serialize_vector(&mut payload, receiver);

        serde::serialize_u8(&mut payload, WITHDRAW);
        payload
    }

    /// Decode withdraw or borrow
    public fun decode_withdraw_payload(app_payload: vector<u8>): (u16, u64, u64, DolaAddress, DolaAddress, u8) {
        let index = 0;
        let data_len;

        data_len = 2;
        let source_chain_id = serde::deserialize_u16(&serde::vector_slice(&app_payload, index, index + data_len));
        index = index + data_len;

        data_len = 8;
        let nonce = serde::deserialize_u64(&serde::vector_slice(&app_payload, index, index + data_len));
        index = index + data_len;

        data_len = 8;
        let amount = serde::deserialize_u64(&serde::vector_slice(&app_payload, index, index + data_len));
        index = index + data_len;

        data_len = 2;
        let pool_address_length = serde::deserialize_u16(&serde::vector_slice(&app_payload, index, index + data_len));
        index = index + data_len;

        data_len = (pool_address_length as u64);
        let pool_address = dola_address::decode_dola_address(
            serde::vector_slice(&app_payload, index, index + data_len)
        );
        index = index + data_len;

        data_len = 2;
        let receive_length = serde::deserialize_u16(&serde::vector_slice(&app_payload, index, index + data_len));
        index = index + data_len;

        data_len = (receive_length as u64);
        let receiver = dola_address::decode_dola_address(serde::vector_slice(&app_payload, index, index + data_len));
        index = index + data_len;

        data_len = 1;
        let lending_call_type = serde::deserialize_u8(&serde::vector_slice(&app_payload, index, index + data_len));
        index = index + data_len;

        assert!(lending_call_type == WITHDRAW, EINVALID_CALL_TYPE);
        assert!(index == vector::length(&app_payload), EINVALID_LENGTH);

        (source_chain_id, nonce, amount, pool_address, receiver, lending_call_type)
    }

    /// Encode liquidate
    public fun encode_liquidate_payload(
        source_chain_id: u16,
        nonce: u64,
        withdraw_pool: DolaAddress,
        liquidate_user_id: u64,
    ): vector<u8> {
        let payload = vector::empty<u8>();

        serde::serialize_u16(&mut payload, source_chain_id);
        serde::serialize_u64(&mut payload, nonce);

        let withdraw_pool = dola_address::encode_dola_address(withdraw_pool);
        serde::serialize_u16(&mut payload, (vector::length(&withdraw_pool) as u16));
        serde::serialize_vector(&mut payload, withdraw_pool);

        serde::serialize_u64(&mut payload, liquidate_user_id);

        serde::serialize_u8(&mut payload, LIQUIDATE);
        payload
    }

    /// Decode liquidate
    public fun decode_liquidate_payload(app_payload: vector<u8>): (u16, u64, DolaAddress, u64, u8) {
        let index = 0;
        let data_len;

        data_len = 2;
        let source_chain_id = serde::deserialize_u16(&serde::vector_slice(&app_payload, index, index + data_len));
        index = index + data_len;

        data_len = 8;
        let nonce = serde::deserialize_u64(&serde::vector_slice(&app_payload, index, index + data_len));
        index = index + data_len;

        data_len = 2;
        let withdraw_pool_length = serde::deserialize_u16(&serde::vector_slice(&app_payload, index, index + data_len));
        index = index + data_len;

        data_len = (withdraw_pool_length as u64);
        let withdraw_pool = dola_address::decode_dola_address(
            serde::vector_slice(&app_payload, index, index + data_len)
        );
        index = index + data_len;

        data_len = 8;
        let liquidate_user_id = serde::deserialize_u64(&serde::vector_slice(&app_payload, index, index + data_len));
        index = index + data_len;

        data_len = 1;
        let lending_call_type = serde::deserialize_u8(&serde::vector_slice(&app_payload, index, index + data_len));
        index = index + data_len;

        assert!(lending_call_type == LIQUIDATE, EINVALID_CALL_TYPE);
        assert!(index == vector::length(&app_payload), EINVALID_LENGTH);

        (source_chain_id, nonce, withdraw_pool, liquidate_user_id, lending_call_type)
    }

    /// Encode manage collateral payload
    public fun encode_manage_collateral_payload(
        sender: DolaAddress,
        dola_pool_ids: vector<u16>,
        lending_call_type: u8
    ): vector<u8> {
        let payload = vector::empty<u8>();

        let sender = dola_address::encode_dola_address(sender);
        serde::serialize_u16(&mut payload, (vector::length(&sender) as u16));
        serde::serialize_vector(&mut payload, sender);

        let pool_ids_length = vector::length(&dola_pool_ids);
        serde::serialize_u16(&mut payload, (pool_ids_length as u16));
        let i = 0;
        while (i < pool_ids_length) {
            serde::serialize_u16(&mut payload, *vector::borrow(&dola_pool_ids, i));
            i = i + 1;
        };

        serde::serialize_u8(&mut payload, lending_call_type);
        payload
    }

    /// Decode manage collateral payload
    public fun decode_manage_collateral_payload(
        payload: vector<u8>
    ): (DolaAddress, vector<u16>, u8) {
        let index = 0;
        let data_len;

        data_len = 2;
        let sender_length = serde::deserialize_u16(&serde::vector_slice(&payload, index, index + data_len));
        index = index + data_len;

        data_len = (sender_length as u64);
        let sender = dola_address::decode_dola_address(serde::vector_slice(&payload, index, index + data_len));
        index = index + data_len;

        data_len = 2;
        let pool_ids_length = serde::deserialize_u16(&serde::vector_slice(&payload, index, index + data_len));
        index = index + data_len;

        let i = 0;
        let dola_pool_ids = vector::empty<u16>();
        while (i < pool_ids_length) {
            data_len = 2;
            let dola_pool_id = serde::deserialize_u16(&serde::vector_slice(&payload, index, index + data_len));
            vector::push_back(&mut dola_pool_ids, dola_pool_id);
            index = index + data_len;
            i = i + 1;
        };

        data_len = 1;
        let lending_call_type = serde::deserialize_u8(&serde::vector_slice(&payload, index, index + data_len));
        index = index + data_len;

        assert!(index == vector::length(&payload), EINVALID_LENGTH);
        (sender, dola_pool_ids, lending_call_type)
    }
}
