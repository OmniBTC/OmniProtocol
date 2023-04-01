from __future__ import annotations

import base64
import copy
import functools
import hashlib
import json
import multiprocessing
import os
import time
import traceback
from pathlib import Path
from typing import Union, List, Dict
from pprint import pprint
from retrying import retry

from dotenv import dotenv_values

from atomicwrites import atomic_write

import yaml
import toml

from sui_brownie.account import Account
from sui_brownie.parallelism import ThreadExecutor
from sui_brownie import bcs
from sui_brownie.bcs import IntentMessage, Intent, NONE, TransactionData, TransactionDataV1, TransactionKind, \
    SuiAddress, GasData, ObjectRef, ObjectID, SequenceNumber, ObjectDigest, U64, TransactionExpiration, \
    ProgrammableTransaction, Command, Identifier, Argument, U16, ProgrammableMoveCall, TypeTag, StructTag, CallArg, \
    ObjectArg, SharedObject, Bool, encode_list, Pure, IntentScope, IntentVersion, AppId, TransferObjects, SplitCoins, \
    NestedResult
from .sui_client import SuiClient

_load_project = []

_cache_file_lock = multiprocessing.Lock()


class AttributeDict:
    """Dictionaries that can be indexed by  '.' to index the dictionary"""

    def __init__(self, data=None):
        if isinstance(data, dict):
            self.data = data
        else:
            self.data = {}

    def __getitem__(self, item):
        return self.data[item]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __getattr__(self, item):
        return self.data[item]

    def __deepcopy__(self, memodict={}):

        return AttributeDict(copy.deepcopy(self.data))


class DefaultDict(dict):
    def __init__(self, default=None):
        self.default = default
        super().__init__()

    def __getitem__(self, item):
        if item not in self:
            super(DefaultDict, self).__setitem__(item, copy.deepcopy(self.default))
        return super(DefaultDict, self).__getitem__(item)

    def __len__(self):
        return len(self.keys())

    def keys(self):
        data = list(super().keys())
        if "default" in data:
            del data["default"]
        return data


class NonDupList(list):
    def append(self, __object) -> None:
        if __object not in self:
            super(NonDupList, self).append(__object)


class SuiObject:
    __single_object: Dict[str, SuiObject] = dict()

    def __init__(self,
                 package_id: str,
                 module_name: str,
                 struct_name: str
                 ):
        self.package_id = package_id
        self.module_name = module_name
        self.struct_name = struct_name
        self.package_name = ""
        assert str(self) not in self.__single_object, f"{package_id} has exist, use 'from_data' create"

    @classmethod
    def from_data(
            cls,
            package_id: str,
            module_name: str,
            struct_name: str
    ) -> SuiObject:
        data = f"{package_id}::{module_name}::{struct_name}"
        if data not in cls.__single_object:
            cls.__single_object[data] = SuiObject(package_id, module_name, struct_name)
        return cls.__single_object[data]

    @classmethod
    def from_type(cls, data: str) -> SuiObject:
        """
        :param data:
            0xb5189942a34446f1d037b446df717987e20a5717::main1::Hello
        :return:
        """
        data = cls.normal_type(data)
        data = data.split("::")
        result = data[:2]
        result.append("::".join(data[2:]))

        return cls.from_data(*result)

    @staticmethod
    def normal_package_id(package_id) -> str:
        """
        0x2 -> 0x0000000000000000000000000000000000000000000000000000000000000002
        :param package_id:
        :return:
        """
        if package_id == "0x2":
            return package_id
        if package_id[:2] == "0x" and len(package_id[2:]) < 64:
            package_id = f"0x{'0' * (64 - len(package_id[2:]))}{package_id[2:]}"
        return package_id

    @classmethod
    def normal_type(cls, data: str):
        """
        0xb5189942a34446f1d037b446df717987e20a5717::main1::Hello -> SuiObject
        :param data:
        :return:
        """
        data = data.split("::")
        for k in range(len(data)):
            index = data[k].find("0x")
            data[k] = data[k][:index] + cls.normal_package_id(data[k][index:])
        return "::".join(data)

    @staticmethod
    def is_sui_object(data: str) -> bool:
        if not isinstance(data, str):
            return False
        return len(data.split("::")) >= 3

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"{self.package_id}::{self.module_name}::{self.struct_name}"

    def __hash__(self):
        return hash(str(self))

    def normal_struct(self):
        """
        0xb5189942a34446f1d037b446df717987e20a5717::main1::Hello -> [Hello]
        0xb5189942a34446f1d037b446df717987e20a5717::main1::Hello<T> -> [Hello, T]
        :return:
        """
        if self.struct_name is None:
            return []
        elif self.struct_name[-1] == ">":
            index = self.struct_name.find("<")
            return [self.struct_name[:index], self.struct_name[index + 1:-1]]
        else:
            return [self.struct_name]


class MoveToml:
    """Easy recovery after package replacement address"""

    def __init__(self, file: str):
        self.file = file
        with open(file, "r") as f:
            data = toml.load(f)
        self.origin_data = data
        self.data = copy.deepcopy(data)

    def __getitem__(self, item):
        return self.data[item]

    def __setitem__(self, key, value):
        self.data[key] = value

    def store(self):
        with open(self.file, "w") as f:
            toml.dump(self.data, f)

    def restore(self):
        with open(self.file, "w") as f:
            toml.dump(self.origin_data, f)

    def get(self, item, default):
        return self.data.get(item, default)

    def keys(self):
        return self.data.keys()


class SuiCliConfig:

    def __init__(self,
                 file,
                 rpc: str,
                 network: str,
                 account: Account):
        if isinstance(file, Path):
            self.file = file
        else:
            self.file = Path(file)
        self.rpc = rpc

        self.network = network.split("-")[-1].lower()
        self.account = account
        self.tmp_keystore = self.file.parent.joinpath(".env.keystore")

    def __enter__(self):
        self.active_config()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file.exists():
            self.file.unlink()

        if self.tmp_keystore.exists():
            self.tmp_keystore.unlink()

    def active_config(self):
        template_config_file = Path(__file__).parent.joinpath("sui_config.template.yaml")
        with open(template_config_file, "r") as f:
            config_data = f.read()

        template_keystore_file = Path(__file__).parent.joinpath("sui_keystore.template.keystore")
        with open(template_keystore_file, "r") as f:
            keystore_data = f.read()
        keystore_data = keystore_data.replace("{keystore}", self.account.keystore())

        with open(self.tmp_keystore, "w") as f:
            f.write(keystore_data)

        config_data = config_data \
            .replace("{file}", str(self.tmp_keystore.absolute())) \
            .replace("{network}", self.network) \
            .replace("{rpc}", self.rpc) \
            .replace("{active_address}", self.account.account_address)
        with open(self.file, "w") as f:
            f.write(config_data)


class ModuleFunction:
    def __init__(self, package: SuiPackage, abi: dict):
        self.package = package
        self.abi = abi

    def __repr__(self):
        return str(self.abi)

    def __call__(self, *args, **kwargs):
        return self.package.project.execute(self.package.package_id, self.abi, *args, **kwargs)

    def __getattr__(self, item):
        assert item in ["simulate", "inspect", "unsafe"], f"{item} attribute not found"
        return functools.partial(getattr(self.package.project, item), self.package.package_id, self.abi)


class ModuleAttributeDict(AttributeDict):
    def __getattr__(self, item):
        if len(_load_project) == 0:
            return []
        project: SuiProject = _load_project[0]
        value = super().__getattr__(item)
        if isinstance(value, SuiObject):
            return project.read_item_from_cache(value)
        elif isinstance(value, ModuleFunction):
            return value
        else:
            return []

    def __deepcopy__(self, memodict={}):
        return ModuleAttributeDict(copy.deepcopy(self.data))


SIGNATURE_SCHEME_TO_FLAG = {
    "ED25519": 0,
    "Secp256k1": 1
}


class TransactionBuild:

    @classmethod
    @functools.lru_cache()
    def project(cls) -> SuiProject:
        assert len(_load_project) > 0
        return _load_project[0]

    @classmethod
    def is_tx_context(cls, param) -> bool:
        if not isinstance(param, dict):
            return False
        if "MutableReference" in param:
            final_arg = param["MutableReference"].get("Struct", dict())
        elif "Reference" in param:
            final_arg = param["Reference"].get("Struct", dict())
        else:
            final_arg = {}
        if final_arg.get("address", None) == "0x2" \
                and final_arg.get("module", None) == "tx_context" \
                and final_arg.get("name", None) == "TxContext":
            return True
        else:
            return False

    @classmethod
    def normal_float(cls, data: list):
        for k in range(len(data)):
            if isinstance(data[k], float):
                assert float(int(data[k])) == data[k], f"{data[k]} must int"
                data[k] = int(data[k])
            elif isinstance(data[k], list):
                cls.normal_float(data[k])

    @classmethod
    def check_args(
            cls,
            abi: dict,
            arguments: list,
            type_arguments: List[str] = None
    ):
        arguments = list(arguments)
        cls.normal_float(arguments)

        if type_arguments is None:
            type_arguments = []
        assert isinstance(list(type_arguments), list) and len(
            abi["typeParameters"]) == len(type_arguments), f"type_arguments error: {abi['type_parameters']}"
        if len(abi["parameters"]) and TransactionBuild.is_tx_context(abi["parameters"][-1]):
            assert len(arguments) == len(abi["parameters"]) - 1, f'arguments error: {abi["parameters"]}'
        else:
            assert len(arguments) == len(abi["parameters"]), f'arguments error: {abi["parameters"]}'

        return arguments, type_arguments

    @classmethod
    def generate_type_arg(cls, type_arg: str) -> TypeTag:
        if type_arg in ["Bool", "U8", "U64", "U128", "Address", "Signer", "U16", "U32", "U256"]:
            return TypeTag(type_arg, NONE())
        elif type_arg.startswith("Vector"):
            child_type_arg = cls.generate_type_arg(type_arg[7:-1])
            return TypeTag("Vector", child_type_arg)
        elif SuiObject.is_sui_object(type_arg):
            sui_object_type = SuiObject.from_type(type_arg)
            address = SuiAddress(sui_object_type.package_id)
            module = Identifier(sui_object_type.module_name)
            struct_name = sui_object_type.struct_name
            type_arg_index = struct_name.index("<")
            if type_arg_index == -1:
                name = Identifier(struct_name)
                type_params = []
            else:
                name = Identifier(struct_name[:type_arg_index])
                type_arg_list = struct_name[type_arg_index + 1:-1].split(",")
                type_arg_list = [v.replace(" ", "") for v in type_arg_list]
                type_params = []
                for v in type_arg_list:
                    child_type_arg = cls.generate_type_arg(v)
                    type_params.append(child_type_arg)
            return TypeTag("Struct", StructTag(address, module, name, type_params))

    @classmethod
    def prepare_gas(cls):
        # gas
        sui_coins = cls.project().client.suix_getCoins(
            cls.project().account.account_address,
            "0x2::sui::SUI",
            None,
            None
        )["data"]
        gas = max(sui_coins, key=lambda x: x["balance"])
        return gas

    @classmethod
    def get_objects(cls, object_ids):
        object_infos = cls.project().client.sui_multiGetObjects(
            object_ids,
            {
                "showType": True,
                "showOwner": True,
                "showPreviousTransaction": False,
                "showDisplay": False,
                "showContent": False,
                "showBcs": False,
                "showStorageRebate": False
            }
        )
        return {object_info["data"]["objectId"]: object_info["data"] for object_info in object_infos}

    @classmethod
    def prepare_object_info(cls, call_arg, abi):
        object_ids = []
        for i in range(len(call_arg)):
            param_type = abi["parameters"][i]
            if isinstance(param_type, dict) and (
                    "Reference" in param_type or "MutableReference" in param_type or "Struct" in param_type):
                object_ids.append(call_arg[i])

        return cls.get_objects(object_ids)

    @classmethod
    def generate_pure_value(cls, param_type, data):
        if param_type in ["Bool", "U8", "U64", "U128", "Address", "Signer", "U16", "U32", "U256"]:
            return getattr(bcs, param_type)(data)
        elif isinstance(param_type, dict) and "Vector" in param_type:
            output = []
            assert isinstance(data, list), f"{param_type}:{data}"
            for i in range(len(data)):
                output.append(cls.generate_pure_value(param_type["Vector"], data[i]))
            return output

    @classmethod
    def generate_call_arg(cls, param_type, data, object_infos):
        if isinstance(param_type, dict) and \
                ("MutableReference" in param_type or
                 "Reference" in param_type or
                 "Struct" in param_type):
            data = object_infos[data]
            if "Shared" in data["owner"]:
                if "MutableReference" in param_type:
                    mutable = Bool(True)
                elif "Reference" in param_type:
                    mutable = Bool(False)
                else:
                    raise ValueError(param_type)
                initial_shared_version = data["owner"]["Shared"]["initial_shared_version"]
                return CallArg("Object", ObjectArg("SharedObject",
                                                   SharedObject(
                                                       ObjectID(data["objectId"]),
                                                       SequenceNumber(initial_shared_version),
                                                       mutable
                                                   )))
            else:
                return CallArg("Object", ObjectArg("ImmOrOwnedObject",
                                                   ObjectRef(
                                                       ObjectID(data["objectId"]),
                                                       SequenceNumber(data["version"]),
                                                       ObjectDigest(data["digest"])
                                                   )))
        else:
            pure_value = cls.generate_pure_value(param_type, data)
            if isinstance(pure_value, list):
                data = list(encode_list(pure_value))
            else:
                data = list(pure_value.encode)
            return CallArg("Pure", Pure(data))

    @classmethod
    def format_type_arg(cls, type_arg):
        if type_arg in ["Bool", "U8", "U64", "U128", "Address", "Signer", "U16", "U32", "U256"]:
            return type_arg
        elif type_arg.startswith("Vector"):
            child_type_arg = cls.format_type_arg(type_arg[7:-1])
            return {"Vector": child_type_arg}
        elif "::" in type_arg:
            return {"Struct": ""}
        else:
            raise ValueError(type_arg)

    @classmethod
    def format_type_args(cls, type_args):
        output = []
        for type_arg in type_args:
            output.append(cls.format_type_arg(type_arg))
        return output

    @classmethod
    def format_vector(cls, param_type: dict, type_args):
        if not isinstance(param_type["Vector"], dict):
            return
        elif "TypeParameter" in param_type["Vector"]:
            param_type["Vector"] = type_args[param_type["Vector"]["TypeParameter"]]
        elif "Vector" in param_type["Vector"]:
            cls.format_vector(param_type["Vector"], type_args)

    @classmethod
    def format_abi_param(cls, abi, type_args):
        abi = copy.deepcopy(abi)
        normal_type_args = cls.format_type_args(type_args)
        for k, param_type in enumerate(abi["parameters"]):
            if not isinstance(param_type, dict):
                continue
            elif "TypeParameter" in param_type:
                abi["parameters"][k] = normal_type_args[param_type["TypeParameter"]]
            elif "Vector" in param_type:
                cls.format_vector(param_type, normal_type_args)
        return abi

    @classmethod
    def command_move_call(
            cls,
            package_id,
            abi,
            type_args,
            call_args,
    ) -> (List[CallArg], List[Command]):
        call_args, type_args = cls.check_args(abi, call_args, type_args)
        # format param
        abi = cls.format_abi_param(abi, type_args)

        # Prepare object
        object_infos = cls.prepare_object_info(call_args, abi)

        # generate inputs
        inputs = []
        for i in range(len(call_args)):
            inputs.append(cls.generate_call_arg(abi["parameters"][i], call_args[i], object_infos))

        # generate commands
        type_arguments = [
            cls.generate_type_arg(v) for v in type_args
        ]
        arguments = [Argument("Input", U16(i)) for i in range(len(call_args))]
        commands = [
            Command("MoveCall", ProgrammableMoveCall(
                ObjectID(package_id),
                Identifier(abi["module_name"]),
                Identifier(abi["func_name"]),
                type_arguments,
                arguments
            ))
        ]
        return inputs, commands

    @classmethod
    def build_intent_message(
            cls,
            sender,
            inputs,
            commands,
            gas_price: int,
            gas_budget,
    ) -> IntentMessage:
        gas = cls.prepare_gas()
        programmable_transaction = ProgrammableTransaction(inputs, commands)

        payment = [ObjectRef(
            ObjectID(gas["coinObjectId"]),
            SequenceNumber(gas["version"]),
            ObjectDigest(gas["digest"])
        )]
        owner = SuiAddress(sender)
        price = U64(gas_price)
        budget = U64(gas_budget)
        expiration = TransactionExpiration("NONE", NONE())
        transaction_data_v1 = TransactionDataV1(TransactionKind("ProgrammableTransaction", programmable_transaction),
                                                SuiAddress(sender),
                                                GasData(
                                                    payment,
                                                    owner,
                                                    price,
                                                    budget
                                                ),
                                                expiration
                                                )
        transaction_data = TransactionData("V1", transaction_data_v1)

        msg = IntentMessage(
            Intent(IntentScope("TransactionData", NONE()),
                   IntentVersion("V0", NONE()),
                   AppId("Sui", NONE())),
            transaction_data
        )
        return msg

    @classmethod
    def move_call(
            cls,
            sender,
            package_id,
            abi,
            type_args,
            call_args,
            gas_price: int,
            gas_budget,
    ) -> IntentMessage:
        inputs, commands = cls.command_move_call(package_id, abi, type_args, call_args)
        return cls.build_intent_message(sender, inputs, commands, gas_price, gas_budget)

    @classmethod
    def transfer_object(
            cls,
            sender,
            object_id,
            recipient,
            gas_price,
            gas_budget
    ) -> IntentMessage:
        data = cls.get_objects([object_id])[object_id]
        # generate inputs
        inputs = [
            CallArg(
                "Pure", Pure(
                    list(SuiAddress(recipient).encode)
                )),
            CallArg("Object", ObjectArg("ImmOrOwnedObject",
                                        ObjectRef(
                                            ObjectID(data["objectId"]),
                                            SequenceNumber(data["version"]),
                                            ObjectDigest(data["digest"])
                                        )))
        ]
        # generate commands
        arguments = [Argument("Input", U16(i)) for i in range(len(inputs))]
        commands = [
            Command("TransferObjects", TransferObjects(
                arguments[1:],
                arguments[0]
            ))
        ]
        return cls.build_intent_message(sender, inputs, commands, gas_price, gas_budget)

    @classmethod
    def pay_sui(
            cls,
            sender,
            recipients,
            amounts,
            gas_price,
            gas_budget
    ) -> IntentMessage:

        # generate inputs
        inputs = [CallArg(
            "Pure", Pure(
                list(U64(int(v)).encode)
            )) for v in amounts]
        arguments = [Argument("Input", U16(i)) for i in range(len(inputs))]
        commands = [
            Command("SplitCoins", SplitCoins(
                Argument("GasCoin", NONE()),
                arguments
            ))
        ]
        for i in range(len(recipients)):
            inputs.append(CallArg(
                "Pure", Pure(
                    list(SuiAddress(recipients[i]).encode)
                )))
            coins = [Argument("NestedResult", NestedResult(U16(0), U16(i)))]
            commands.append(
                Command("TransferObjects", TransferObjects(
                    coins,
                    inputs[-1]
                ))
            )
        return cls.build_intent_message(sender, inputs, commands, gas_price, gas_budget)

    @classmethod
    def command_split_coins(
            cls,
            sender,
            coin_object_id,
            split_amounts,
            gas_price: int,
            gas_budget,
    ):
        # gas = cls.prepare_gas()
        # object_infos = cls.get_objects([coin_object_id])
        # # generate inputs
        # inputs = [CallArg(
        #     "Pure", Pure(
        #         SuiAddress(recipient)
        #     )
        # )]
        # for object_id in range(len(object_ids)):
        #     data = object_infos[object_id]
        #     inputs.append(CallArg("Object", ObjectArg("ImmOrOwnedObject",
        #                                               ObjectRef(
        #                                                   ObjectID(object_id),
        #                                                   SequenceNumber(data["version"]),
        #                                                   ObjectDigest(data["digest"])
        #                                               ))))
        #
        # # generate commands
        # arguments = [Argument("Input", U16(i)) for i in range(len(inputs))]
        # commands = [
        #     Command("SplitCoins", SplitCoins(
        #         arguments[1:],
        #         arguments[0]
        #     ))
        # ]
        # programmable_transaction = ProgrammableTransaction(inputs, commands)
        #
        # payment = [ObjectRef(
        #     ObjectID(gas["coinObjectId"]),
        #     SequenceNumber(gas["version"]),
        #     ObjectDigest(gas["digest"])
        # )]
        # owner = SuiAddress(sender)
        # price = U64(gas_price)
        # budget = U64(gas_budget)
        # expiration = TransactionExpiration("NONE", NONE())
        # transaction_data_v1 = TransactionDataV1(TransactionKind("ProgrammableTransaction", programmable_transaction),
        #                                         SuiAddress(sender),
        #                                         GasData(
        #                                             payment,
        #                                             owner,
        #                                             price,
        #                                             budget
        #                                         ),
        #                                         expiration
        #                                         )
        # transaction_data = TransactionData("V1", transaction_data_v1)
        # msg = IntentMessage(
        #     Intent(IntentScope("TransactionData", NONE()),
        #            IntentVersion("V0", NONE()),
        #            AppId("Sui", NONE())),
        #     transaction_data
        # )
        # return msg
        pass

    @staticmethod
    def merge_coins(

    ):
        pass

    @staticmethod
    def publish(

    ):
        pass

    @staticmethod
    def make_move_vec(

    ):
        pass

    @staticmethod
    def upgrade(
    ):
        pass


class SuiPackage:
    def __init__(
            self,
            package_id: str = None,
            package_name: str = None,
            package_path: Union[Path, str] = None,
    ):
        assert len(_load_project) > 0, "Project not init"
        self.project: SuiProject = _load_project[0]
        assert package_id is not None or package_path is not None
        if package_path is None:
            assert package_name is not None, f"Package path is none, set package name"
        self.package_id = package_id
        self.package_name = package_name

        self.package_path = package_path
        # package_path is not none
        self.move_toml_file = self.package_path.joinpath("Move.toml") if self.package_path is not None else None
        self.move_toml: MoveToml = MoveToml(str(self.move_toml_file)) if self.move_toml_file is not None else None
        if self.package_name is None and self.move_toml is not None:
            self.package_name = self.move_toml["package"]["name"]

        # module name -> struct -> SuiObjectType
        #             -> func  -> () : call transaction
        #                      -> simulate : simulate transaction
        #                      -> inspect : inspect value
        # Record package struct and func abi
        self.modules = DefaultDict(ModuleAttributeDict())
        self.abi = None

        if self.package_id is not None:
            self.update_abi()

        # # # # # # filter result
        self.filter_result_key = ["disassembled", "signers_map"]

    def __getattr__(self, item):
        if item in self.modules:
            return self.modules[item]
        else:
            raise ValueError(f"{item} not found")

    def __repr__(self):
        return self.package_id

    def load_package(self):
        if self.package_path is None:
            self.package_path = self.project.project_path
        elif isinstance(self.package_path, str):
            self.package_path = Path(self.package_path)
        else:
            self.package_path = self.package_path

    def update_abi(self):
        if self.package_id is None:
            return

        result = None
        for i in range(10):
            time.sleep(3)
            try:
                result = self.project.client.sui_getNormalizedMoveModulesByPackage(self.package_id)
                break
            except Exception as e:
                print(f"Warning not found package:{self.package_id} info, err:{e}, retry")

        self.abi = result
        for module_name in result:
            # Update
            for struct_name in result[module_name].get("structs", dict()):
                # refuse process include type param object
                if len(result[module_name]["structs"][struct_name].get("type_parameters", [])):
                    continue
                object_type = SuiObject.from_type(f"{self.package_id}::{module_name}::{struct_name}")
                object_type.package_name = self.package_name
                self.modules[module_name][struct_name] = object_type
            for func_name in result[module_name].get("exposedFunctions", dict()):
                abi = result[module_name]["exposedFunctions"][func_name]
                abi["module_name"] = module_name
                abi["func_name"] = func_name
                self.modules[module_name][func_name] = ModuleFunction(self, abi)

    # ####### Publish

    def replace_toml(self, move_toml: MoveToml, replace_address: dict = None):
        package_name = move_toml["package"]["name"]
        if package_name in replace_address:
            if replace_address[package_name] is not None:
                move_toml["package"]["published-at"] = replace_address[package_name]
            elif self.project.search_package(package_name) is not None:
                move_toml["package"]["published-at"] = self.project.search_package(package_name)
            else:
                assert False, "Replace address not found for published-at"
        for k in list(move_toml.get("addresses", dict()).keys()):
            if k in replace_address:
                if replace_address[k] is not None:
                    move_toml["addresses"][k] = replace_address[k]
                else:
                    assert False, "Replace address is None for addresses"
        return move_toml

    def replace_addresses(
            self,
            replace_address: dict = None,
            output: dict = None
    ) -> dict:
        if replace_address is None:
            return output
        if output is None:
            output = dict()
        current_move_toml = MoveToml(str(self.move_toml_file))
        if current_move_toml["package"]["name"] in output:
            return output
        output[current_move_toml["package"]["name"]] = current_move_toml

        # process current move toml
        self.replace_toml(current_move_toml, replace_address)

        # process dependencies move toml
        for k in list(current_move_toml.keys()):
            if "dependencies" == k:
                for d in list(current_move_toml[k].keys()):
                    # process local
                    if "local" in current_move_toml[k][d]:
                        local_path = self.package_path \
                            .joinpath(current_move_toml[k][d]["local"])
                        assert local_path.exists(), f"{local_path.absolute()} not found"
                        dep_move_toml = SuiPackage(package_path=local_path)
                        dep_move_toml.replace_addresses(replace_address, output)
                    # process remote
                    else:
                        git_index = current_move_toml[k][d]["git"].rfind("/")
                        git_path = current_move_toml[k][d]["git"][:git_index + 1]
                        git_file = current_move_toml[k][d]["git"][git_index + 1:]
                        if "subdir" not in current_move_toml[k][d]:
                            git_file = f"{d}.git"
                            sub_dir = ""
                        else:
                            sub_dir = current_move_toml[k][d]["subdir"]
                        git_file = (git_path + git_file + f"_{current_move_toml[k][d]['rev']}") \
                            .replace("://", "___") \
                            .replace("/", "_").replace(".", "_")
                        remote_path = Path(f"{os.environ.get('HOME')}/.move") \
                            .joinpath(git_file) \
                            .joinpath(sub_dir)
                        assert remote_path.exists(), f"{remote_path.absolute()} not found"
                        dep_move_toml = SuiPackage(package_path=remote_path)
                        dep_move_toml.replace_addresses(replace_address, output)

        for k in output:
            output[k].store()
        return output

    def format_dict(self, data):
        for k in list(data.keys()):
            if k in self.filter_result_key:
                del data[k]
                continue
            if isinstance(data[k], list):
                self.format_list(data[k])
            elif isinstance(data[k], dict):
                self.format_dict(data[k])

    def format_list(self, data):
        for v in data:
            if isinstance(v, list):
                self.format_list(v)
            elif isinstance(v, dict):
                self.format_dict(v)

    def format_result(self, data):
        if data is None:
            return
        if isinstance(data, list):
            self.format_list(data)
        if isinstance(data, dict):
            self.format_dict(data)
        return data

    @retry(stop_max_attempt_number=3, wait_random_min=500, wait_random_max=1000)
    def publish_package(
            self,
            gas_budget=10000000,
            replace_address: dict = None
    ):
        replace_tomls = self.replace_addresses(replace_address=replace_address, output=dict())
        view = f"Publish {self.package_name}"
        print("\n" + "-" * 50 + view + "-" * 50)
        try:
            with self.project.cli_config as cof:
                cmd = f"sui client --client.config {cof.file.absolute()} publish " \
                      f" --gas-budget {gas_budget} " \
                      f"--abi --json {self.package_path.absolute()}"
                with os.popen(cmd) as f:
                    result = f.read()
                try:
                    result = json.loads(result[result.find("{"):])
                except:
                    pprint(f"Publish error:\n{result}")
                    raise
                self.project.update_object_index(result.get("effects", dict()))
                for d in result.get("objectChanges", []):
                    if d["type"] == "published":
                        self.package_id = d["packageId"]
                        self.project.add_package(self)
                        self.update_abi()
            result = self.format_result(result)
            pprint(result)
            assert self.package_id is not None, f"Package id not found"
            print("-" * (100 + len(view)))
            print("\n")
            for k in replace_tomls:
                replace_tomls[k].restore()
        except:
            for k in replace_tomls:
                replace_tomls[k].restore()
            traceback.print_exc()
            raise
        return result


class SuiProject:
    def __init__(
            self,
            project_path: Union[Path, str] = Path.cwd(),
            network: str = "sui-testnet"
    ):
        self.project_path = project_path
        self.network = network

        self.config = {}
        self.network_config = {}
        self.client: SuiClient = None
        self.accounts: Dict[str, Account] = {}
        self.__active_account = None
        self.packages: Dict[str, List[SuiPackage]] = DefaultDict([])

        self.cache_dir = Path(os.environ.get('HOME')).joinpath(".sui-brownie")
        if not self.cache_dir.exists():
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir.joinpath("objects.json")
        self.cache_objects: Dict[Union[SuiObject, str], Dict[str, list]] = DefaultDict(DefaultDict(NonDupList()))
        self.cli_config_file = self.cache_dir.joinpath(".cli.yaml")
        self.cli_config: SuiCliConfig = None

        self.load_config()
        self.reload_cache()

        _load_project.append(self)

    def read_item_from_cache(self, item: Union[str, SuiObject]):
        if item in self.cache_objects:
            if self.account.account_address in self.cache_objects[item]:
                return self.cache_objects[item][self.account.account_address]
            elif "Shared" in self.cache_objects[item]:
                return self.cache_objects[item]["Shared"]
            else:
                raise ValueError(f"item not found for {self.account.account_address}")
        elif isinstance(item, str):
            try:
                sui_object = SuiObject.from_type(item)
                if sui_object in self.cache_objects:
                    return self.read_item_from_cache(sui_object)
                else:
                    raise ValueError(f"{item} not found")
            except:
                raise ValueError(f"{item} not found")
        else:
            raise ValueError(f"{item} not found")

    def __getitem__(self, item):
        return self.read_item_from_cache(item)

    def __getattr__(self, item):
        return self.read_item_from_cache(item)

    def active_account(self, account_name):
        assert account_name in self.accounts, f"{account_name} not found in {list(self.accounts.keys())}"
        self.__active_account = self.accounts[account_name]
        print(f"\nActive account {account_name}, address:{self.__active_account.account_address}")
        self.cli_config = SuiCliConfig(self.cli_config_file, str(self.client.endpoint), self.network, self.account)

    @property
    def account(self) -> Account:
        if self.__active_account is None:
            print("account not active")
        return self.__active_account

    def load_config(self):
        # Check path
        if isinstance(self.project_path, Path):
            self.project_path = self.project_path
        else:
            self.project_path = Path(self.project_path)
        assert self.project_path.joinpath("brownie-config.yaml").exists(), "Project not found brownie-config.yaml"

        # Read config
        with self.project_path.joinpath("brownie-config.yaml").open() as fp:
            self.config = yaml.safe_load(fp)
        assert "networks" in self.config, f"networks not found in brownie-config.yaml"
        assert self.network in self.config["networks"], f"{self.network} not found in brownie-config.yaml"
        self.network_config = self.config["networks"][self.network]

        # Read count
        env_file = self.config["dotenv"] if "dotenv" in self.config else ".env"
        env = dotenv_values(self.project_path.joinpath(env_file))
        assert "sui_wallets" in self.config, "Unassigned activation accounts"
        assert "from_mnemonic" in self.config["sui_wallets"], "Wallet config format error"
        for account_name, env_name in self.config["sui_wallets"]["from_mnemonic"].items():
            env_name = env_name.replace("$", "").replace("{", "").replace("}", "")
            assert env_name in env, f"{env_name} env not exist"
            self.accounts[account_name] = Account(mnemonic=env[env_name])

        # Create client
        assert "node_url" in self.network_config, "Endpoint not config"
        self.client = SuiClient(base_url=self.network_config["node_url"], timeout=30)

    def reload_cache(self):
        data = self.read_cache()
        for k1 in data:
            try:
                sui_object = SuiObject.from_type(k1)
                for k2 in data[k1]:
                    for object_id in data[k1][k2]:
                        self.add_object_to_cache(sui_object, k2, object_id, persist=False)
            except:
                for k2 in data[k1]:
                    for package_id in data[k1][k2]:
                        self.add_package_to_cache(k1, package_id, persist=False)

    def read_cache(self):
        if not self.cache_file.exists():
            return {}

        with open(str(self.cache_file), "r") as f:
            try:
                data = json.load(f)
            except Exception as e:
                print(f"Warning: read cache occurs {e}")
                return {}
        return data

    def write_cache(self):
        def write_cache_worker():
            output = DefaultDict({})
            for k1 in self.cache_objects:
                for k2 in self.cache_objects[k1]:
                    output[str(k1)][str(k2)] = self.cache_objects[k1][k2]
            while True:
                try:
                    _cache_file_lock.acquire(timeout=10)
                    with atomic_write(str(self.cache_file), overwrite=True) as f:
                        json.dump(output, f, indent=1, sort_keys=True)
                    _cache_file_lock.release()
                    break
                except Exception as e:
                    print(f"Write cache fail, err:{e}")
                    time.sleep(1)

        pt = ThreadExecutor(executor=1, mode="all")
        pt.run([write_cache_worker])

    def add_object_to_cache(self, sui_object: SuiObject, owner, sui_object_id, persist=True):
        self.cache_objects[sui_object][owner].append(sui_object_id)
        if persist:
            self.write_cache()

    def add_package_to_cache(self, package_name, package_id, persist=True):
        assert package_name is not None, f"{package_id} name is none"
        self.cache_objects[package_name]["Shared"].append(package_id)
        if persist:
            self.write_cache()

    def add_package(self, package: SuiPackage):
        self.packages[package.package_id].append(package)
        self.add_package_to_cache(package.package_name, package.package_id)

    def search_package(self, package_name):
        package_names = {k: True for k in list(self.cache_objects.keys()) if isinstance(k, str)}
        if package_name in package_names:
            data = self.cache_objects[package_name].get("Shared", [])
            if len(data):
                return data[-1]
        return None

    def _execute(
            self,
            tx_bytes,
            signatures,
            request_type="WaitForLocalExecution",
            module=None,
            function=None,
    ):
        """
        :param tx_bytes:
        :param signatures:
        :param request_type:
            Execute the transaction and wait for results if desired. Request types:
            1. ImmediateReturn: immediately returns a response to client without waiting for any execution results.
            Note the transaction may fail without being noticed by client in this mode. After getting the response,
            the client may poll the node to check the result of the transaction.
            2. WaitForTxCert: waits for TransactionCertificate and then return to client.
            3. WaitForEffectsCert: waits for TransactionEffectsCert and then return to client.
            This mode is a proxy for transaction finality.
            4. WaitForLocalExecution: waits for TransactionEffectsCert and make sure the node executed the transaction
            locally before returning the client. The local execution makes sure this node is aware of this transaction
            when client fires subsequent queries. However if the node fails to execute the transaction locally in a
            timely manner, a bool type in the response is set to False to indicated the case
        :return:
        """
        result = self.client.sui_executeTransactionBlock(
            tx_bytes,
            signatures,
            {
                "showInput": True,
                "showRawInput": True,
                "showEffects": True,
                "showEvents": True,
                "showObjectChanges": True,
                "showBalanceChanges": True
            },
            request_type
        )

        if result["effects"]["status"]["status"] != "success":
            pprint(result)
        assert result["effects"]["status"]["status"] == "success"
        self.update_object_index(result["effects"])
        print(f"Execute {module}::{function} success, transactionDigest: {result['effects']['transactionDigest']}")
        return result

    def generate_signature(self, msg: bytes):
        sig_scheme = "ED25519"
        hasher = hashlib.blake2b(digest_size=32)
        hasher.update(msg)
        msg = hasher.digest()
        serialized_sig = []
        serialized_sig.extend(bytes([SIGNATURE_SCHEME_TO_FLAG[sig_scheme]]))
        serialized_sig.extend(list(self.account.sign(msg).get_bytes()))
        serialized_sig.extend(list(self.account.public_key().get_bytes()))
        serialized_sig_base64 = base64.b64encode(bytes(serialized_sig)).decode("ascii")
        return serialized_sig_base64

    def unsafe(
            self,
            package_id,
            abi: dict,
            *arguments,
            type_arguments: List[str] = None,
            gas_budget=10000000,
    ):
        result = self.construct_transaction(
            package_id=package_id,
            abi=abi,
            arguments=arguments,
            type_arguments=type_arguments,
            gas_budget=gas_budget)
        # Simulate before execute
        tx_bytes = result["txBytes"]
        self.client.sui_dryRunTransactionBlock(tx_bytes)

        # sig
        msg = bytes([IntentScope.TransactionData[1], IntentVersion.V0[1], AppId.Sui[1]]
                    + list(base64.b64decode(tx_bytes)))
        serialized_sig_base64 = self.generate_signature(msg)

        # Execute
        print(f'\nExecute transaction {abi["module_name"]}::{abi["func_name"]}, waiting...')
        return self._execute(result["txBytes"],
                             signatures=[serialized_sig_base64],
                             module=abi["module_name"], function=abi["func_name"])

    def execute(
            self,
            package_id,
            abi: dict,
            *arguments,
            type_arguments: List[str] = None,
            gas_price=1000,
            gas_budget=10000000,
    ):
        # Construct
        msg = TransactionBuild.move_call(
            self.account.account_address,
            package_id,
            abi,
            type_arguments,
            arguments,
            gas_price=gas_price,
            gas_budget=gas_budget
        )
        # simulate
        tx_bytes = base64.b64encode(msg.value.encode).decode("ascii")
        self.client.sui_dryRunTransactionBlock(tx_bytes)

        # Sig
        serialized_sig_base64 = self.generate_signature(msg.encode)

        # Execute
        print(f'\nExecute transaction {abi["module_name"]}::{abi["func_name"]}, waiting...')
        return self._execute(tx_bytes, [serialized_sig_base64], module=abi["module_name"], function=abi["func_name"])

    def update_object_index(self, result):
        """
        Update Object cache after contract deployment and transaction execution
        :param result: effects
            {
              "messageVersion": "v1",
              "status": {
                "status": "success"
              },
              "mutated": [
                {
                  "owner": {
                    "AddressOwner": "0x61fbb5b4f342a40bdbf87fe4a946b9e38d18cf8ffc7b0000b975175c7b6a9576"
                  },
                  "reference": {
                    "objectId": "0xe8d8c7ce863f313da3dbd92a83ef26d128b88fe66bf26e0e0d09cdaf727d1d84",
                    "version": 2,
                    "digest": "EnRQXe1hDGAJCFyF2ds2GmPHdvf9V6yxf24LisEsDkYt"
                  }
                }
              ]
            }
        :return:
        """
        object_ids = []
        pprint(result)
        assert result["status"]["status"] == "success", result["status"]["status"]
        for k in ["created", "mutated"]:
            for d in result.get(k, dict()):
                if "reference" in d and "objectId" in d["reference"]:
                    object_ids.append(d["reference"]["objectId"])
        if len(object_ids):
            sui_object_infos = self.client.sui_multiGetObjects(object_ids, {
                "showType": True,
                "showOwner": True,
                "showPreviousTransaction": False,
                "showDisplay": False,
                "showContent": False,
                "showBcs": False,
                "showStorageRebate": False
            })
            for sui_object_info in sui_object_infos:
                if "error" in sui_object_info:
                    continue
                sui_object_id = sui_object_info["data"]["objectId"]
                if sui_object_info["data"]["type"] == "package":
                    continue
                else:
                    sui_object = SuiObject.from_type(sui_object_info["data"]["type"])
                    if "Shared" in sui_object_info["data"]["owner"]:
                        self.add_object_to_cache(sui_object, "Shared", sui_object_id)
                    elif "AddressOwner" in sui_object_info["data"]["owner"]:
                        owner = sui_object_info["data"]["owner"]["AddressOwner"]
                        self.add_object_to_cache(sui_object, owner, sui_object_id)

    def get_account_sui(self):
        result = self.client.suix_getCoins(self.account.account_address, "0x2::sui::SUI", None, None)
        return {v["coinObjectId"]: v["balance"] for v in result["data"]}

    def construct_transaction(
            self,
            package_id,
            abi: dict,
            arguments: list,
            type_arguments: List[str] = None,
            gas_budget=10000000,
    ):
        arguments, type_arguments = TransactionBuild.check_args(abi, arguments, type_arguments)

        for k in range(len(arguments)):
            # Process U64, U128, U256
            if abi["parameters"][k] in ["U64", "U128", "U256"]:
                arguments[k] = str(arguments[k])

        object_ids = self.get_account_sui()
        gas_object = max(list(object_ids.keys()), key=lambda x: object_ids[x])
        result = self.client.unsafe_moveCall(
            self.account.account_address,
            package_id,
            abi["module_name"],
            abi["func_name"],
            type_arguments,
            arguments,
            gas_object,
            gas_budget,
            None
        )
        return result

    def simulate(
            self,
            abi: dict,
            *arguments,
            type_arguments: List[str] = None,
            gas_budget=10000000,
    ):
        result = self.construct_transaction(abi, arguments, type_arguments, gas_budget)
        return self.client.sui_dryRunTransactionBlock(result["txBytes"])

    def inspect(
            self,
            abi: dict,
            *arguments,
            type_arguments: List[str] = None,
            gas_budget=10000000,
    ):
        result = self.construct_transaction(abi, arguments, type_arguments, gas_budget)
        return self.client.sui_devInspectTransactionBlock(
            self.account.account_address,
            result["txBytes"],
            None,
            None
        )

    def unsafe_pay_all_sui(self, recipient=None, gas_budget=10000000):
        if recipient is None:
            recipient = self.account.account_address
        input_coins = list(self.get_account_sui().keys())
        result = self.client.unsafe_payAllSui(self.account.account_address, input_coins, recipient, gas_budget)

        # Simulate before execute
        tx_bytes = result["txBytes"]
        self.client.sui_dryRunTransactionBlock(tx_bytes)

        # sig
        msg = bytes([IntentScope.TransactionData[1], IntentVersion.V0[1], AppId.Sui[1]]
                    + list(base64.b64decode(tx_bytes)))
        serialized_sig_base64 = self.generate_signature(msg)

        # Execute
        print(f'\nExecute transaction unsafe::pay_all_sui, waiting...')
        return self._execute(result["txBytes"],
                             signatures=[serialized_sig_base64],
                             module="unsafe",
                             function="pay_all_sui"
                             )

    def unsafe_pay_sui(self, amounts, recipients=None, gas_budget=10000000):
        if recipients is None:
            recipients = [self.account.account_address] * len(amounts)
        input_coins = list(self.get_account_sui().keys())
        amounts = [str(v) for v in amounts]
        result = self.client.unsafe_paySui(
            self.account.account_address,
            input_coins,
            recipients,
            amounts,
            gas_budget=gas_budget
        )
        # simulate
        tx_bytes = result["txBytes"]
        self.client.sui_dryRunTransactionBlock(tx_bytes)

        # Sig
        msg = bytes([IntentScope.TransactionData[1], IntentVersion.V0[1], AppId.Sui[1]]
                    + list(base64.b64decode(tx_bytes)))
        serialized_sig_base64 = self.generate_signature(msg)

        # Execute
        print(f'\nExecute transaction unsafe_transfer::transfer_object, waiting...')
        return self._execute(tx_bytes, [serialized_sig_base64], module="unsafe_transfer", function="transfer_object")

    def pay_sui(self, amounts, recipients=None, gas_price=1000, gas_budget=10000000):
        if recipients is None:
            recipients = [self.account.account_address] * len(amounts)
        msg = TransactionBuild.pay_sui(
            self.account.account_address,
            recipients,
            amounts,
            gas_price=gas_price,
            gas_budget=gas_budget
        )
        # simulate
        tx_bytes = base64.b64encode(msg.value.encode).decode("ascii")
        self.client.sui_dryRunTransactionBlock(tx_bytes)

        # Sig
        serialized_sig_base64 = self.generate_signature(msg.encode)

        # Execute
        print(f'\nExecute transaction unsafe_transfer::transfer_object, waiting...')
        return self._execute(tx_bytes, [serialized_sig_base64], module="unsafe_transfer", function="transfer_object")

    def unsafe_transfer_object(self, object_id, recipient, gas_price=1000, gas_budget=10000000):
        result = self.client.unsafe_transferObject(
            self.account.account_address,
            object_id,
            gas=None,
            gas_budget=gas_budget,
            recipient=recipient)
        # simulate
        tx_bytes = result["txBytes"]
        self.client.sui_dryRunTransactionBlock(tx_bytes)

        # Sig
        msg = bytes([IntentScope.TransactionData[1], IntentVersion.V0[1], AppId.Sui[1]]
                    + list(base64.b64decode(tx_bytes)))
        serialized_sig_base64 = self.generate_signature(msg)

        # Execute
        print(f'\nExecute transaction unsafe_transfer::transfer_object, waiting...')
        return self._execute(tx_bytes, [serialized_sig_base64], module="unsafe_transfer", function="transfer_object")

    def transfer_object(self, object_id, recipient, gas_price=1000, gas_budget=10000000):
        msg = TransactionBuild.transfer_object(
            self.account.account_address,
            object_id,
            recipient,
            gas_price=gas_price,
            gas_budget=gas_budget)

        # simulate
        tx_bytes = base64.b64encode(msg.value.encode).decode("ascii")
        self.client.sui_dryRunTransactionBlock(tx_bytes)

        # Sig
        serialized_sig_base64 = self.generate_signature(msg.encode)

        # Execute
        print(f'\nExecute transaction transfer::transfer_object, waiting...')
        return self._execute(tx_bytes, [serialized_sig_base64], module="transfer", function="transfer_object")
