import asyncio.exceptions
import base64
import datetime
import functools
import json
import logging
import multiprocessing
import time
import traceback
from pathlib import Path
from pprint import pprint

import brownie
import ccxt
import requests
from dotenv import dotenv_values
from gql import gql, Client
from gql.client import log as gql_client_logs
from gql.transport.aiohttp import AIOHTTPTransport, log as gql_logs
from pymongo import MongoClient
from retrying import retry
from sui_brownie import Argument, U16
from sui_brownie.parallelism import ProcessExecutor

import dola_ethereum_sdk
import dola_ethereum_sdk.init as dola_ethereum_init
import dola_ethereum_sdk.load as dola_ethereum_load
import dola_sui_sdk
import dola_sui_sdk.init as dola_sui_init
import dola_sui_sdk.lending as dola_sui_lending
import dola_sui_sdk.load as dola_sui_load
from dola_sui_sdk.load import sui_project

G_wei = 1e9


class ColorFormatter(logging.Formatter):
    grey = '\x1b[38;21m'
    green = '\x1b[92m'
    yellow = '\x1b[38;5;226m'
    red = '\x1b[38;5;196m'
    bold_red = '\x1b[31;1m'
    reset = '\x1b[0m'

    def __init__(self, fmt):
        super().__init__()
        self.fmt = fmt
        self.FORMATS = {
            logging.DEBUG: self.grey + self.fmt + self.reset,
            logging.INFO: self.green + self.fmt + self.reset,
            logging.WARNING: self.yellow + self.fmt + self.reset,
            logging.ERROR: self.red + self.fmt + self.reset,
            logging.CRITICAL: self.bold_red + self.fmt + self.reset
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def init_logger():
    global logger
    FORMAT = '%(asctime)s - %(funcName)s - %(levelname)s - %(name)s: %(message)s'
    logger = logging.getLogger()
    logger.setLevel("INFO")
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    ch.setFormatter(ColorFormatter(FORMAT))

    logger.addHandler(ch)

    gql_client_logs.setLevel(logging.WARNING)
    gql_logs.setLevel(logging.WARNING)


def init_markets():
    global kucoin
    kucoin = ccxt.kucoin()
    kucoin.load_markets()


def fix_requests_ssl():
    requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS = 'ALL'


@retry
def get_token_price(token):
    if token == "eth":
        return float(kucoin.fetch_ticker("ETH/USDT")['close'])
    elif token == "bnb":
        return float(kucoin.fetch_ticker("BNB/USDT")['close'])
    elif token == "matic":
        return float(kucoin.fetch_ticker("MATIC/USDT")['close'])
    elif token == "apt":
        return float(kucoin.fetch_ticker("APT/USDT")['close'])
    elif token == "sui":
        return float(kucoin.fetch_ticker("SUI/USDT")['close'])


def get_token_decimal(token):
    if token in ['eth', 'matic', 'bnb']:
        return 18
    elif token == 'apt':
        return 8
    elif token == 'sui':
        return 9


def get_fee_value(amount, token='sui'):
    price = get_token_price(token)
    decimal = get_token_decimal(token)
    return price * amount / pow(10, decimal)


def get_fee_amount(value, token='sui'):
    price = get_token_price(token)
    decimal = get_token_decimal(token)
    return int(value / price * pow(10, decimal))


def get_call_name(app_id, call_type):
    if app_id == 0:
        if call_type == 0:
            return "binding"
        elif call_type == 1:
            return "unbinding"
    elif app_id == 1:
        if call_type == 0:
            return "supply"
        elif call_type == 1:
            return "withdraw"
        elif call_type == 2:
            return "borrow"
        elif call_type == 3:
            return "repay"
        elif call_type == 4:
            return "liquidate"
        elif call_type == 5:
            return "as_collateral"
        elif call_type == 6:
            return "cancel_as_collateral"


def get_dola_network(dola_chain_id):
    if dola_chain_id == 0:
        return "sui-mainnet"
    elif dola_chain_id == 5:
        return "polygon-main"
    elif dola_chain_id == 23:
        return "arbitrum-main"
    elif dola_chain_id == 24:
        return "optimism-main"
    else:
        return "unknown"


def get_gas_token(network='polygon-test'):
    if "sui" in network:
        return "sui"
    elif "aptos" in network:
        return "apt"
    elif "polygon" in network:
        return "matic"
    elif "bsc" in network:
        return "bnb"
    else:
        return "eth"


def execute_sui_core(call_name, vaa, relay_fee):
    gas = 0
    executed = False
    status = "Unknown"
    feed_nums = 0
    digest = ""
    if call_name == "binding":
        gas, executed, status, digest = dola_sui_lending.core_binding(vaa, relay_fee)
    elif call_name == "unbinding":
        gas, executed, status, digest = dola_sui_lending.core_unbinding(vaa, relay_fee)
    elif call_name == "supply":
        gas, executed, status, digest = dola_sui_lending.core_supply(vaa, relay_fee)
    elif call_name == "withdraw":
        gas, executed, status, feed_nums, digest = dola_sui_lending.core_withdraw(vaa, relay_fee)
    elif call_name == "borrow":
        gas, executed, status, feed_nums, digest = dola_sui_lending.core_borrow(vaa, relay_fee)
    elif call_name == "repay":
        gas, executed, status, digest = dola_sui_lending.core_repay(vaa, relay_fee)
    elif call_name == "liquidate":
        gas, executed, status, feed_nums, digest = dola_sui_lending.core_liquidate(vaa, relay_fee)
    elif call_name == "as_collateral":
        gas, executed, status, digest = dola_sui_lending.core_as_collateral(vaa, relay_fee)
    elif call_name == "cancel_as_collateral":
        gas, executed, status, feed_nums, digest = dola_sui_lending.core_cancel_as_collateral(
            vaa, relay_fee)
    return gas, executed, status, feed_nums, digest


def init_accounts_and_lock():
    global account_index
    global index_lock

    m = multiprocessing.Manager()

    index_lock = m.Lock()
    account_index = m.Value('i', 0)


def rotate_accounts():
    global account_index
    index_lock.acquire()
    index = account_index.get()
    index += 1
    num = index % 4
    sui_project.active_account(f"Relayer{num}")
    account_index.set(index)
    index_lock.release()


class RelayRecord:

    def __init__(self):
        db = mongodb()
        self.db = db['RelayRecord']

    def add_other_record(self, src_chain_id, src_tx_id, nonce, call_name, block_number, sequence, vaa, relay_fee,
                         start_time):
        record = {
            "src_chain_id": src_chain_id,
            "src_tx_id": src_tx_id,
            "nonce": nonce,
            "call_name": call_name,
            "block_number": block_number,
            "sequence": sequence,
            "vaa": vaa,
            "relay_fee": relay_fee,
            "core_tx_id": "",
            "core_costed_fee": 0,
            "status": "false",
            "reason": "Unknown",
            "start_time": start_time,
            "end_time": "",
        }
        self.db.insert_one(record)

    def add_sui_withdraw_record(self, nonce, call_name, vaa, relay_fee, dst_pool_address):
        record = {
            "src_chain_id": 0,
            "nonce": nonce,
            "call_name": call_name,
            "sequence": nonce,
            "relay_fee": relay_fee,
            "withdraw_chain_id": "",
            "withdraw_sequence": 0,
            "withdraw_vaa": vaa,
            "withdraw_pool": dst_pool_address,
            "withdraw_costed_fee": 0,
            "status": "withdraw",
            "reason": "Unknown"
        }
        self.db.insert_one(record)

    def add_sui_other_record(self, nonce, call_name, sequence, vaa, relay_fee):
        record = {
            "src_chain_id": 0,
            "nonce": nonce,
            "call_name": call_name,
            "sequence": sequence,
            "vaa": vaa,
            "relay_fee": relay_fee,
            "core_costed_fee": 0,
            "status": "false",
            "reason": "Unknown"
        }
        self.db.insert_one(record)

    def add_withdraw_record(self, src_chain_id, src_tx_id, nonce, call_name, block_number, sequence, vaa, relay_fee,
                            start_time):
        record = {
            "src_chain_id": src_chain_id,
            "src_tx_id": src_tx_id,
            "nonce": nonce,
            "call_name": call_name,
            "block_number": block_number,
            "sequence": sequence,
            "vaa": vaa,
            "relay_fee": relay_fee,
            "core_tx_id": "",
            "core_costed_fee": 0,
            "withdraw_chain_id": "",
            "withdraw_tx_id": "",
            "withdraw_sequence": 0,
            "withdraw_vaa": "",
            "withdraw_pool": "",
            "withdraw_costed_fee": 0,
            "status": "false",
            "reason": "Unknown",
            "start_time": start_time,
            "end_time": "",
        }
        self.db.insert_one(record)

    def add_wait_record(self, src_chain_id, src_tx_hash, nonce, sequence, block_number, relay_fee_value, date):
        record = {
            'src_chain_id': src_chain_id,
            'src_tx_id': src_tx_hash,
            'nonce': nonce,
            'sequence': sequence,
            'block_number': block_number,
            'relay_fee': relay_fee_value,
            'status': 'waitForVaa',
            'start_time': date,
            'end_time': "",
        }
        self.db.insert_one(record)

    def update_record(self, filter, update):
        self.db.update_one(filter, update)

    def find_one(self, filter):
        return self.db.find_one(filter)

    def find(self, filter):
        return self.db.find(filter)


class GasRecord:

    def __init__(self):
        db = mongodb()
        self.db = db['GasRecord']

    def add_gas_record(self, src_chain_id, nonce, dst_chain_id, call_name, core_gas=0, feed_nums=0):
        record = {
            'src_chain_id': src_chain_id,
            'nonce': nonce,
            'dst_chain_id': dst_chain_id,
            'call_name': call_name,
            'core_gas': core_gas,
            'withdraw_gas': 0,
            'feed_nums': feed_nums
        }
        self.db.insert_one(record)

    def update_record(self, filter, update):
        self.db.update_one(filter, update)

    def find(self, filter):
        return self.db.find(filter)


ZERO_FEE = int(1e18)


def sui_portal_watcher():
    dola_sui_sdk.set_dola_project_path(Path("../.."))
    local_logger = logger.getChild("[sui_portal_watcher]")
    local_logger.info("Start to watch sui portal ^-^")

    relay_record = RelayRecord()
    gas_record = GasRecord()

    sui_network = sui_project.network
    while True:
        try:
            relay_events = dola_sui_init.query_portal_relay_event()

            for event in relay_events:
                fields = event['parsedJson']

                call_type = fields["call_type"]
                call_name = get_call_name(1, int(call_type))
                nonce = fields['nonce']

                if not relay_record.find_one({'src_chain_id': 0, 'nonce': nonce}):
                    relay_fee_amount = int(fields['fee_amount'])
                    relay_fee = get_fee_value(relay_fee_amount, 'sui')

                    sequence = fields['sequence']
                    dst_pool = fields['dst_pool']
                    dst_chain_id = int(dst_pool['dola_chain_id'])
                    dst_pool_address = f"0x{bytes(dst_pool['dola_address']).hex()}"

                    if call_name in ['withdraw', 'borrow']:
                        vaa = get_signed_vaa_by_wormhole(
                            WORMHOLE_EMITTER_ADDRESS[sui_network], sequence, sui_network)
                        relay_record.add_sui_withdraw_record(nonce, call_name, vaa, relay_fee, dst_pool_address)
                    else:
                        vaa = get_signed_vaa_by_wormhole(WORMHOLE_EMITTER_ADDRESS['sui-mainnet-pool'], sequence,
                                                         sui_network)
                        relay_record.add_sui_other_record(nonce, call_name, sequence, vaa, relay_fee)

                    gas_record.add_gas_record(0, nonce, dst_chain_id, call_name)

                    local_logger.info(
                        f"Have a {call_name} from sui to {get_dola_network(dst_chain_id)}, nonce: {nonce}")
        except Exception as e:
            local_logger.error(f"Error: {e}")
        time.sleep(3)


def wormhole_vaa_guardian(network="polygon-test"):
    dola_ethereum_sdk.set_dola_project_path(Path("../.."))
    dola_ethereum_sdk.set_ethereum_network(network)

    local_logger = logger.getChild(f"[{network}_wormhole_vaa_guardian]")
    local_logger.info("Start to wait wormhole vaa ^-^")

    relay_record = RelayRecord()

    src_chain_id = NET_TO_WORMHOLE_CHAINID[network]
    emitter_address = dola_ethereum_load.wormhole_adapter_pool_package(network).address
    wormhole = dola_ethereum_load.womrhole_package(network)

    while True:
        wait_vaa_txs = list(relay_record.find({'status': 'waitForVaa', 'src_chain_id': src_chain_id}).sort(
            "block_number", 1))

        for tx in wait_vaa_txs:
            try:
                nonce = tx['nonce']
                sequence = tx['sequence']
                block_number = tx['block_number']

                vaa = get_signed_vaa_by_wormhole(
                    emitter_address, sequence, network)

                vm = wormhole.parseVM(vaa)
                # parse payload
                payload = list(vm)[7]

                app_id = payload[1]
                call_type = payload[-1]
                call_name = get_call_name(app_id, call_type)

                relay_fee = tx['relay_fee']

                if call_name in ['withdraw', 'borrow']:
                    relay_record.add_withdraw_record(src_chain_id, tx['src_tx_id'], nonce, call_name, block_number,
                                                     sequence, vaa,
                                                     relay_fee, tx['start_time'])
                else:
                    relay_record.add_other_record(src_chain_id, tx['src_tx_id'], nonce, call_name, block_number,
                                                  sequence, vaa,
                                                  relay_fee, tx['start_time'])

                current_timestamp = int(time.time())
                date = str(datetime.datetime.fromtimestamp(current_timestamp))
                relay_record.update_record({'status': 'waitForVaa', 'src_chain_id': src_chain_id, 'nonce': nonce},
                                           {'$set': {'status': 'dropped', 'end_time': date}})
                local_logger.info(
                    f"Have a {call_name} transaction from {network}, sequence: {nonce}")
            except Exception as e:
                local_logger.warning(f"Error: {e}")
        time.sleep(5)


def eth_portal_watcher(network="polygon-test"):
    dola_ethereum_sdk.set_dola_project_path(Path("../.."))
    dola_ethereum_sdk.set_ethereum_network(network)

    local_logger = logger.getChild(f"[{network}_portal_watcher]")
    local_logger.info(f"Start to read {network} pool vaa ^-^")

    relay_record = RelayRecord()

    src_chain_id = NET_TO_WORMHOLE_CHAINID[network]
    wormhole = dola_ethereum_load.womrhole_package(network)
    emitter_address = dola_ethereum_load.wormhole_adapter_pool_package(network).address
    lending_portal = dola_ethereum_load.lending_portal_package(network).address
    system_portal = dola_ethereum_load.system_portal_package(network).address

    graphql_url = dola_ethereum_init.graphql_url(network)
    transport = AIOHTTPTransport(url=graphql_url)

    # Create a GraphQL client using the defined transport
    client = Client(transport=transport, fetch_schema_from_transport=True)

    # query latest block number
    result = list(relay_record.find({'src_chain_id': src_chain_id}).sort("block_number", -1).limit(1))
    latest_relay_block_number = result[0]['block_number'] if result else 0
    limit = 5

    while True:
        try:
            result = list(relay_record.find({'src_chain_id': src_chain_id}).sort("block_number", -1).limit(1))
            latest_relay_block_number = result[0]['block_number'] if result else latest_relay_block_number

            # query relay events from latest relay block number + 1 to actual latest block number
            relay_events = list(client.execute(graph_query(latest_relay_block_number, limit))['relayEvents']) \
                           or dola_ethereum_init.query_relay_event_by_get_logs(lending_portal, system_portal,
                                                                               latest_relay_block_number)

            for event in relay_events:
                nonce = int(event['nonce'])
                sequence = int(event['sequence'])

                # check if the event has been recorded
                if not list(relay_record.find(
                        {
                            'src_chain_id': src_chain_id,
                            'nonce': nonce,
                            "sequence": sequence,
                        }
                )):
                    block_number = int(event['blockNumber'])
                    src_tx_hash = event['transactionHash']
                    timestamp = int(event['blockTimestamp'])
                    relay_fee_amount = int(event['amount'])
                    date = str(datetime.datetime.utcfromtimestamp(timestamp))

                    gas_token = get_gas_token(network)
                    relay_fee_value = get_fee_value(relay_fee_amount, gas_token)

                    # get vaa
                    try:
                        vaa = get_signed_vaa_by_wormhole(
                            emitter_address, sequence, network)
                    except Exception as e:
                        relay_record.add_wait_record(src_chain_id, src_tx_hash, nonce, sequence, block_number,
                                                     relay_fee_value,
                                                     date)
                        local_logger.warning(f"Warning: {e}")
                        continue
                    # parse vaa

                    vm = wormhole.parseVM(vaa)
                    # parse payload
                    payload = list(vm)[7]

                    app_id = payload[1]
                    call_type = payload[-1]
                    call_name = get_call_name(app_id, call_type)

                    if call_name in ['withdraw', 'borrow']:
                        relay_record.add_withdraw_record(src_chain_id, src_tx_hash, nonce, call_name, block_number,
                                                         sequence, vaa, relay_fee_value, date)
                    else:
                        relay_record.add_other_record(src_chain_id, src_tx_hash, nonce, call_name, block_number,
                                                      sequence, vaa, relay_fee_value, date)

                    local_logger.info(
                        f"Have a {call_name} transaction from {network}, sequence: {sequence}")
        except asyncio.exceptions.TimeoutError:
            local_logger.warning("GraphQL request timeout")
        except Exception as e:
            local_logger.error(f"Error: {e}")
            traceback.print_exc()
        finally:
            time.sleep(2)


def pool_withdraw_watcher():
    dola_sui_sdk.set_dola_project_path(Path("../.."))
    local_logger = logger.getChild("[pool_withdraw_watcher]")
    local_logger.info("Start to read withdraw vaa ^-^")

    relay_record = RelayRecord()

    sui_network = sui_project.network
    while True:
        try:
            relay_events = dola_sui_init.query_core_relay_event()

            for event in relay_events:
                fields = event['parsedJson']

                source_chain_id = int(fields['source_chain_id'])
                source_chain_nonce = int(fields['source_chain_nonce'])

                if relay_record.find_one(
                        {'src_chain_id': source_chain_id, 'nonce': source_chain_nonce, 'status': 'waitForWithdraw'}):
                    call_type = fields["call_type"]
                    call_name = get_call_name(1, int(call_type))
                    src_network = get_dola_network(source_chain_id)
                    sequence = int(fields['sequence'])
                    vaa = get_signed_vaa_by_wormhole(
                        WORMHOLE_EMITTER_ADDRESS[sui_network], sequence, sui_network)

                    dst_pool = fields['dst_pool']
                    dst_chain_id = int(dst_pool['dola_chain_id'])
                    dst_pool_address = f"0x{bytes(dst_pool['dola_address']).hex()}"

                    relay_record.update_record({'src_chain_id': source_chain_id, 'nonce': source_chain_nonce},
                                               {"$set": {'status': 'withdraw', 'withdraw_vaa': vaa,
                                                         'withdraw_chain_id': dst_chain_id,
                                                         'withdraw_sequence': sequence,
                                                         'withdraw_pool': dst_pool_address}})

                    local_logger.info(
                        f"Have a {call_name} from {src_network} to {get_dola_network(dst_chain_id)}, nonce: {source_chain_nonce}")
        except Exception as e:
            local_logger.error(f"Error: {e}")
        time.sleep(1)


def sui_core_executor():
    dola_sui_sdk.set_dola_project_path(Path("../.."))
    local_logger = logger.getChild("[sui_core_executor]")
    local_logger.info("Start to relay pool vaa ^-^")

    relay_record = RelayRecord()
    gas_record = GasRecord()

    while True:
        relay_transactions = relay_record.find({"status": "false"})
        for tx in relay_transactions:
            try:
                relay_fee_value = tx['relay_fee']
                relay_fee = get_fee_amount(relay_fee_value)
                call_name = tx['call_name']

                rotate_accounts()
                # check relayer balance
                if sui_total_balance() < int(1e9):
                    local_logger.warning(
                        f"Relayer balance is not enough, need {relay_fee_value} sui")
                    time.sleep(5)
                    continue

                # If no gas record exists, relay once for free.
                if not list(gas_record.find({'src_chain_id': tx['src_chain_id'], 'call_name': call_name})):
                    relay_fee = ZERO_FEE

                gas, executed, status, feed_nums, digest = execute_sui_core(
                    call_name, tx['vaa'], relay_fee)

                # Relay not existent feed_num tx for free.
                if not executed and status == 'success' and not list(gas_record.find(
                        {'src_chain_id': tx['src_chain_id'], 'call_name': call_name,
                         'feed_nums': feed_nums})):
                    relay_fee = ZERO_FEE
                    gas, executed, status, feed_nums, digest = execute_sui_core(
                        call_name, tx['vaa'], relay_fee)

                gas_price = int(
                    sui_project.client.suix_getReferenceGasPrice())
                gas_limit = int(gas / gas_price)

                gas_record.add_gas_record(tx['src_chain_id'], tx['nonce'], 0, call_name, gas_limit, feed_nums)

                if executed and status == 'success':
                    core_costed_fee = get_fee_value(gas, 'sui')
                    relay_fee_value = get_fee_value(relay_fee, 'sui')

                    timestamp = int(time.time())
                    date = str(datetime.datetime.utcfromtimestamp(timestamp))
                    if call_name in ["withdraw", "borrow"]:
                        relay_record.update_record({'vaa': tx['vaa']},
                                                   {"$set": {'relay_fee': relay_fee_value,
                                                             'status': 'waitForWithdraw',
                                                             'end_time': date,
                                                             'core_tx_id': digest,
                                                             'core_costed_fee': core_costed_fee}})
                    else:
                        relay_record.update_record({'vaa': tx['vaa']},
                                                   {"$set": {'relay_fee': relay_fee_value, 'status': 'success',
                                                             'core_tx_id': digest,
                                                             'core_costed_fee': core_costed_fee,
                                                             'end_time': date}})

                    local_logger.info("Execute sui core success! ")
                else:
                    relay_record.update_record({'vaa': tx['vaa']},
                                               {"$set": {'status': 'fail', 'reason': status}})
                    local_logger.warning("Execute sui core fail! ")
                    local_logger.warning(f"status: {status}")
            except AssertionError as e:
                status = eval(str(e))
                relay_record.update_record({'vaa': tx['vaa']},
                                           {"$set": {'status': 'fail', 'reason': status['effects']['status']['error']}})
                local_logger.warning("Execute sui core fail! ")
                local_logger.warning(f"status: {status}")
            except Exception as e:
                traceback.print_exc()
                local_logger.error(f"Execute sui core fail\n {e}")
        time.sleep(1)


def sui_pool_executor():
    dola_sui_sdk.set_dola_project_path(Path("../.."))
    local_logger = logger.getChild("[sui_pool_executor]")
    local_logger.info("Start to relay sui withdraw vaa ^-^")

    relay_record = RelayRecord()
    gas_record = GasRecord()

    while True:
        relay_transactions = relay_record.find(
            {"status": "withdraw", "withdraw_chain_id": 0})
        for withdraw_tx in relay_transactions:
            try:
                core_costed_fee = (
                    withdraw_tx['core_costed_fee']
                    if "core_costed_fee" in withdraw_tx
                    else 0
                )
                relay_fee_value = withdraw_tx['relay_fee'] - core_costed_fee

                available_gas_amount = get_fee_amount(relay_fee_value, 'sui')

                source_chain_id = withdraw_tx['src_chain_id']
                source_nonce = withdraw_tx['nonce']
                token_name = withdraw_tx['withdraw_pool']
                vaa = withdraw_tx['withdraw_vaa']

                rotate_accounts()
                # check relayer balance
                if sui_total_balance() < int(1e9):
                    local_logger.warning(
                        f"Relayer balance is not enough, need {relay_fee_value} sui")
                    time.sleep(5)
                    continue

                gas_used, executed, digest, timestamp = dola_sui_lending.pool_withdraw(
                    vaa, token_name, available_gas_amount)

                timestamp = int(time.time())
                tx_gas_amount = gas_used

                gas_price = int(
                    sui_project.client.suix_getReferenceGasPrice())
                gas_limit = int(tx_gas_amount / gas_price)
                gas_record.update_record({'src_chain_id': source_chain_id, 'nonce': source_nonce},
                                         {"$set": {'withdraw_gas': gas_limit, 'dst_chain_id': 0}})

                if executed:
                    withdraw_cost_fee = get_fee_value(tx_gas_amount, 'sui')

                    date = str(datetime.datetime.utcfromtimestamp(timestamp))
                    relay_record.update_record({'withdraw_vaa': vaa},
                                               {"$set": {'status': 'success', 'withdraw_cost_fee': withdraw_cost_fee,
                                                         'end_time': date, 'withdraw_tx_id': digest}})

                    local_logger.info("Execute sui withdraw success! ")
                    local_logger.info(
                        f"token: {token_name} source_chain: {source_chain_id} nonce: {source_nonce}")
                    local_logger.info(
                        f"relay fee: {relay_fee_value}, consumed fee: {get_fee_value(tx_gas_amount)}")
                else:
                    call_name = withdraw_tx['call_name']
                    local_logger.warning(
                        "Execute withdraw fail on sui, not enough relay fee! ")
                    local_logger.warning(
                        f"Need gas fee: {get_fee_value(tx_gas_amount)}, but available gas fee: {relay_fee_value}"
                    )
                    local_logger.warning(
                        f"call: {call_name} source_chain: {source_chain_id}, nonce: {source_nonce}")
            except Exception as e:
                traceback.print_exc()
                local_logger.error(f"Execute sui pool withdraw fail\n {e}")
        time.sleep(3)


def eth_pool_executor():
    dola_ethereum_sdk.set_dola_project_path(Path("../.."))
    local_logger = logger.getChild("[eth_pool_executor]")
    local_logger.info("Start to relay eth withdraw vaa ^-^")

    relay_record = RelayRecord()
    gas_record = GasRecord()

    while True:
        relay_transactions = relay_record.find(
            {"status": "withdraw", "withdraw_chain_id": {"$ne": 0}})
        for withdraw_tx in relay_transactions:
            try:
                dola_chain_id = withdraw_tx['withdraw_chain_id']
                network = get_dola_network(dola_chain_id)
                dola_ethereum_sdk.set_ethereum_network(network)

                ethereum_wormhole_bridge = dola_ethereum_load.wormhole_adapter_pool_package(
                    network)
                ethereum_account = dola_ethereum_sdk.get_account()
                local_logger.info(
                    f"Ethereum account: {ethereum_account.address}")
                source_chain_id = withdraw_tx['src_chain_id']
                source_chain = get_dola_network(source_chain_id)
                source_nonce = withdraw_tx['nonce']

                vaa = withdraw_tx['withdraw_vaa']

                core_costed_fee = (
                    withdraw_tx['core_costed_fee']
                    if "core_costed_fee" in withdraw_tx
                    else 0
                )
                relay_fee_value = withdraw_tx['relay_fee'] - core_costed_fee
                available_gas_amount = get_fee_amount(relay_fee_value, get_gas_token(network))
                # check relayer balance
                if network in ['arbitrum-main', 'optimism-main'] and int(ethereum_account.balance()) < int(0.01 * 1e18):
                    local_logger.warning(
                        f"Relayer balance is not enough, need 0.01 {get_gas_token(network)}, but available {ethereum_account.balance()}")
                    time.sleep(5)
                    continue

                gas_price = int(brownie.web3.eth.gas_price)
                gas_used = ethereum_wormhole_bridge.receiveWithdraw.estimate_gas(
                    vaa, {"from": ethereum_account})

                gas_record.update_record({'src_chain_id': source_chain_id, 'nonce': source_nonce},
                                         {"$set": {'withdraw_gas': gas_used, 'dst_chain_id': dola_chain_id}})

                tx_gas_amount = int(gas_used) * gas_price

                result = ethereum_wormhole_bridge.receiveWithdraw(
                    vaa, {"from": ethereum_account})

                tx_id = result.txid
                timestamp = time.time()
                date = str(datetime.datetime.utcfromtimestamp(int(timestamp)))

                withdraw_cost_fee = get_fee_value(tx_gas_amount, get_gas_token(network))
                relay_record.update_record({'withdraw_vaa': withdraw_tx['withdraw_vaa']},
                                           {"$set": {'status': 'success', 'withdraw_cost_fee': withdraw_cost_fee,
                                                     'end_time': date, 'withdraw_tx_id': tx_id}})

                local_logger.info(f"Execute {network} withdraw success! ")
                local_logger.info(
                    f"source: {source_chain} nonce: {source_nonce}")
                local_logger.info(
                    f"relay fee: {relay_fee_value}, consumed fee: {get_fee_value(tx_gas_amount, get_gas_token(network))}")

                if available_gas_amount < tx_gas_amount:
                    local_logger.warning(
                        f"Execute withdraw success on {get_dola_network(dola_chain_id)}, but not enough relay fee! ")
                    local_logger.warning(
                        f"Need gas fee: {get_fee_value(tx_gas_amount, get_gas_token(network))}, but available gas fee: {relay_fee_value}")
                    call_name = withdraw_tx['call_name']
                    local_logger.warning(
                        f"call: {call_name} source: {source_chain}, nonce: {source_nonce}")
            except ValueError as e:
                local_logger.warning(f"Execute eth pool withdraw fail\n {e}")
                relay_record.update_record({'withdraw_vaa': withdraw_tx['withdraw_vaa']},
                                           {"$set": {'status': 'fail', 'reason': str(e)}})
            except Exception as e:
                traceback.print_exc()
                local_logger.error(f"Execute eth pool withdraw fail\n {e}")


def get_unrelay_txs(src_chain_id, call_name, limit):
    db = mongodb()
    relay_record = db['RelayRecord']

    if int(limit) > 0:
        result = list(relay_record.find(
            {'src_chain_id': int(src_chain_id), 'call_name': call_name, 'status': 'fail', 'reason': 'success'},
            {'_id': False}).limit(
            int(limit)))
    else:
        result = list(relay_record.find(
            {'src_chain_id': int(src_chain_id), 'call_name': call_name, 'status': 'fail', 'reason': 'success'},
            {'_id': False}))

    return {'result': result}


def get_unrelay_tx_by_sequence(src_chain_id, sequence):
    db = mongodb()
    relay_record = db['RelayRecord']

    return {'result': list(
        relay_record.find(
            {
                'src_chain_id': int(src_chain_id),
                'status': 'fail',
                'reason': 'success',
                'sequence': int(sequence),
            },
            {'_id': False}
        )
    )}


def get_max_relay_fee(src_chain_id, dst_chain_id, call_name):
    db = mongodb()
    gas_record = db['GasRecord']

    result = list(gas_record.find(
        {"src_chain_id": int(src_chain_id), "dst_chain_id": int(dst_chain_id), "call_name": call_name}).sort(
        'core_gas', -1).limit(1))

    return calculate_relay_fee(result, int(src_chain_id), int(dst_chain_id))


def get_relay_fee(src_chain_id, dst_chain_id, call_name, feed_num):
    db = mongodb()
    gas_record = db['GasRecord']
    if call_name in ['borrow', 'withdraw', 'cancel_as_collateral']:
        result = list(gas_record.find(
            {"src_chain_id": int(src_chain_id), "dst_chain_id": int(dst_chain_id), "call_name": call_name,
             "feed_nums": int(feed_num)}).sort('nonce', -1).limit(10))
    else:
        result = list(gas_record.find(
            {"src_chain_id": int(src_chain_id), "dst_chain_id": int(dst_chain_id), "call_name": call_name}).sort(
            'nonce', -1).limit(10))
    return calculate_relay_fee(result, int(src_chain_id), int(dst_chain_id))


def calculate_relay_fee(records, src_chain_id, dst_chain_id):
    if not records:
        return {'relay_fee': '0'}

    core_gas = 0
    withdraw_gas = 0
    for record in records:
        core_gas += record['core_gas']
        withdraw_gas += record['withdraw_gas']

    record_len = len(records)
    average_core_gas = int(core_gas / record_len)
    average_withdraw_gas = int(withdraw_gas / record_len)

    sui_gas_price = int(sui_project.client.suix_getReferenceGasPrice())
    core_fee_amount = average_core_gas * sui_gas_price
    core_fee = get_fee_value(core_fee_amount, 'sui')

    dst_net = get_dola_network(dst_chain_id)
    if int(dst_chain_id) == 0:
        gas_price = sui_gas_price
    else:
        dola_ethereum_sdk.set_ethereum_network(dst_net)
        gas_price = int(brownie.web3.eth.gas_price)
    withdraw_fee_amount = average_withdraw_gas * gas_price
    withdraw_fee = get_fee_value(withdraw_fee_amount, get_gas_token(dst_net))

    relay_fee = core_fee + withdraw_fee
    src_net = get_dola_network(src_chain_id)

    return {'relay_fee': str(get_fee_amount(relay_fee, get_gas_token(src_net)))}


def sui_vaa_payload(vaa):
    wormhole = dola_sui_load.wormhole_package()

    result = sui_project.batch_transaction_inspect(
        actual_params=[
            sui_project.network_config['objects']['WormholeState'],
            list(bytes.fromhex(vaa.replace("0x", ""))),
            dola_sui_init.clock()
        ],
        transactions=[
            [
                wormhole.vaa.parse_and_verify,
                [
                    Argument("Input", U16(0)),
                    Argument("Input", U16(1)),
                    Argument("Input", U16(2)),
                ],
                []
            ],
            [
                wormhole.vaa.payload,
                [
                    Argument("Result", U16(0))
                ],
                []
            ]
        ]
    )

    pprint(result)


NET_TO_WORMHOLE_CHAINID = {
    # mainnet
    "mainnet": 2,
    "bsc-main": 4,
    "polygon-main": 5,
    "avax-main": 6,
    "optimism-main": 24,
    "arbitrum-main": 23,
    "aptos-mainnet": 22,
    "sui-mainnet": 21,
    # testnet
    "goerli": 2,
    "bsc-test": 4,
    "polygon-test": 5,
    "avax-test": 6,
    "optimism-test": 24,
    "arbitrum-test": 23,
    "aptos-testnet": 22,
    "sui-testnet": 21,
}

WORMHOLE_EMITTER_ADDRESS = {
    # mainnet
    "optimism-main": "0x94650D61b940496b1BD88767b7B541b1121e0cCF",
    "arbitrum-main": "0x098D26E4d2E98C1Dde14C543Eb6804Fd98Af9CB4",
    "polygon-main": "0x4445c48e9B70F78506E886880a9e09B501ED1E13",
    "sui-mainnet": "0xabbce6c0c2c7cd213f4c69f8a685f6dfc1848b6e3f31dd15872f4e777d5b3e86",
    "sui-mainnet-pool": "0xdd1ca0bd0b9e449ff55259e5bcf7e0fc1b8b7ab49aabad218681ccce7b202bd6",
    # testnet
    "polygon-test": "0xE5230B6bA30Ca157988271DC1F3da25Da544Dd3c",
    "sui-testnet": "0x9031f04d97adacea16a923f20b9348738a496fb98f9649b93f68406bafb2437e",
}


@retry
def get_signed_vaa_by_wormhole(
        emitter: str,
        sequence: int,
        src_net: str = None
):
    """
    Get signed vaa
    :param emitter:
    :param src_net:
    :param sequence:
    :return: dict
        {'vaaBytes': 'AQAAAAEOAGUI...'}
    """
    wormhole_url = sui_project.network_config['wormhole_url']
    emitter_address = dola_sui_init.format_emitter_address(emitter)
    emitter_chainid = NET_TO_WORMHOLE_CHAINID[src_net]

    url = f"{wormhole_url}/v1/signed_vaa/{emitter_chainid}/{emitter_address}/{sequence}"
    response = requests.get(url)

    if 'vaaBytes' not in response.json():
        raise ValueError(f"Get {src_net} signed vaa failed: {response.text}")

    vaa_bytes = response.json()['vaaBytes']
    vaa = base64.b64decode(vaa_bytes).hex()
    return f"0x{vaa}"


def get_signed_vaa(
        sequence: int,
        src_wormhole_id: int = None,
        url: str = None
):
    if url is None:
        url = "http://wormhole-testnet.sherpax.io"
    if src_wormhole_id is None:
        data = {
            "method": "GetSignedVAA",
            "params": [
                str(sequence),
            ]
        }
    else:
        data = {
            "method": "GetSignedVAA",
            "params": [
                str(sequence),
                src_wormhole_id,
            ]
        }
    headers = {'content-type': 'application/json'}
    response = requests.post(url, data=json.dumps(data), headers=headers)
    return response.json()


def get_mongodb_uri():
    env_file = sui_project.config['dotenv']
    env_values = dotenv_values(sui_project.project_path.joinpath(env_file))
    return env_values['MONGODB_URI']


def mongodb():
    mongo_uri = get_mongodb_uri()
    client = MongoClient(mongo_uri)

    return client['DolaProtocol']


def sui_total_balance():
    return int(sui_project.client.suix_getBalance(sui_project.account.account_address, '0x2::sui::SUI')['totalBalance'])


def graph_query(block_number, limit=5):
    return gql(
        f"{{ \
			  relayEvents(where: {{blockNumber_gt: {block_number}}}, orderDirection: asc, orderBy: nonce, first: {limit}) {{ \
				transactionHash \
				blockNumber \
				blockTimestamp \
				nonce \
				sequence \
				amount \
			  }} \
			}}"
    )


def main():
    init_logger()
    init_markets()
    # Use when you need to improve concurrency
    init_accounts_and_lock()

    pt = ProcessExecutor(executor=11)

    pt.run([
        sui_core_executor,
        functools.partial(eth_portal_watcher, "arbitrum-main"),
        functools.partial(wormhole_vaa_guardian, "arbitrum-main"),
        functools.partial(eth_portal_watcher, "optimism-main"),
        functools.partial(wormhole_vaa_guardian, "optimism-main"),
        functools.partial(eth_portal_watcher, "polygon-main"),
        functools.partial(wormhole_vaa_guardian, "polygon-main"),
        sui_portal_watcher,
        pool_withdraw_watcher,
        sui_pool_executor,
        eth_pool_executor,
    ])


# portal watcher insert relay record
# pool withdraw watcher update relay record
# core executor query relay record and execute
# pool executor query relay record and execute

if __name__ == "__main__":
    main()
