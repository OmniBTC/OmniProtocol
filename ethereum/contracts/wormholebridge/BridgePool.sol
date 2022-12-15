// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "../../libraries/LibPool.sol";
import "../../libraries/LibAsset.sol";
import "../../interfaces/IOmniPool.sol";
import "../../interfaces/IWormhole.sol";

contract BridgePool {
    address wormholeBridge;
    uint32 nonce;
    uint16 dolaChainId;
    uint16 wormholeChainId;
    uint8 finality;
    address remoteBridge;
    mapping(bytes32 => bool) completeVAA;

    constructor(
        address _wormholeBridge,
        uint16 _dolaChainId,
        uint16 _wormholeChainId,
        uint8 _finality,
        address _remoteBridge
    ) {
        wormholeBridge = _wormholeBridge;
        dolaChainId = _dolaChainId;
        wormholeChainId = _wormholeChainId;
        finality = _finality;
        remoteBridge = _remoteBridge;
    }

    function wormhole() internal view returns (IWormhole) {
        return IWormhole(wormholeBridge);
    }

    function getWormholeMessageFee() internal view returns (uint256) {
        return IWormhole(wormholeBridge).messageFee();
    }

    function getWormholeBridge() internal view returns (address) {
        return wormholeBridge;
    }

    function getNonce() internal view returns (uint32) {
        return nonce;
    }

    function getFinality() internal view returns (uint8) {
        return finality;
    }

    function increaseNonce() internal {
        nonce += 1;
    }

    function setVAAComplete(bytes32 _hash) internal {
        completeVAA[_hash] = true;
    }

    function isCompleteVAA(bytes32 _hash) internal view returns (bool) {
        return completeVAA[_hash];
    }

    function sendDeposit(
        address pool,
        uint256 amount,
        uint16 appId,
        bytes memory appPayload
    ) external payable {
        bytes memory payload = IOmniPool(pool).depositTo(
            amount,
            appId,
            appPayload
        );
        wormhole().publishMessage{value: msg.value}(
            getNonce(),
            payload,
            getFinality()
        );
        increaseNonce();
    }

    function sendWithdraw(
        address pool,
        uint16 appId,
        bytes memory appPayload
    ) external payable {
        bytes memory payload = IOmniPool(pool).withdrawTo(appId, appPayload);
        IWormhole(wormhole()).publishMessage{value: msg.value}(
            getNonce(),
            payload,
            getFinality()
        );
        increaseNonce();
    }

    function sendDepositAndWithdraw(
        address depositPool,
        uint256 depositAmount,
        address withdrawPool,
        address withdrawUser,
        bytes memory withdrawTokenName,
        uint16 appId,
        bytes memory appPayload
    ) external payable {
        bytes memory payload = IOmniPool(depositPool).depositAndWithdraw(
            depositAmount,
            withdrawPool,
            withdrawUser,
            withdrawTokenName,
            appId,
            appPayload
        );
        IWormhole(wormhole()).publishMessage{value: msg.value}(
            getNonce(),
            payload,
            getFinality()
        );
        increaseNonce();
    }

    function receiveWithdraw(bytes memory vaa) public {
        (IWormhole.VM memory vm, , ) = wormhole().parseAndVerifyVM(vaa);
        require(!isCompleteVAA(vm.hash), "withdraw already completed");
        setVAAComplete(vm.hash);

        LibPool.ReceiveWithdrawPayload memory payload = LibPool
            .decodeReceiveWithdrawPayload(vm.payload);
        IOmniPool(payload.pool).innerWithdraw(payload.user, payload.amount);
    }
}
