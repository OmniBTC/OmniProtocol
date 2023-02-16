module app_manager::app_manager {
    use governance::genesis::GovernanceCap;
    use sui::object::{Self, UID, ID};
    use sui::transfer;
    use sui::tx_context::TxContext;
    use std::vector;

    /// Record all App information
    struct TotalAppInfo has key, store {
        id: UID,
        app_caps: vector<ID>
    }

    /// Giving applications access to the DolaProtocol single pool through AppCap
    struct AppCap has key, store {
        id: UID,
        app_id: u16
    }

    fun init(ctx: &mut TxContext) {
        transfer::share_object(TotalAppInfo {
            id: object::new(ctx),
            app_caps: vector::empty()
        })
    }

    fun register_app(total_app_info: &mut TotalAppInfo, ctx: &mut TxContext): AppCap {
        let id = object::new(ctx);
        vector::push_back(&mut total_app_info.app_caps, object::uid_to_inner(&id));

        let app_id = AppCap {
            id,
            app_id: (vector::length(&total_app_info.app_caps) as u16)
        };

        app_id
    }

    /// Register cap through governance
    public fun register_cap_with_governance(
        _: &GovernanceCap,
        total_app_info: &mut TotalAppInfo,
        ctx: &mut TxContext
    ): AppCap {
        register_app(total_app_info, ctx)
    }

    /// Get app id by app cap
    public fun get_app_id(app_id: &AppCap): u16 {
        app_id.app_id
    }

    /// Destroy app cap
    public fun destroy_app_cap(app_id: AppCap) {
        let AppCap { id, app_id: _ } = app_id;
        object::delete(id);
    }

    #[test_only]
    public fun init_for_testing(ctx: &mut TxContext) {
        init(ctx)
    }

    #[test_only]
    public fun register_app_for_testing(total_app_info: &mut TotalAppInfo, ctx: &mut TxContext): AppCap {
        register_app(total_app_info, ctx)
    }
}
