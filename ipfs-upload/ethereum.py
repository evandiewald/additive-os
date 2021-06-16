import config
import time
from web3 import Web3, HTTPProvider
import web3
import json

AM_License_contract_address = config.AMLICENSE_CONTRACT_ADDRESS
AM_Project_contract_address = config.AMPROJECT_CONTRACT_ADDRESS
wallet_private_key = config.WALLET_PRIVATE_KEY
wallet_address = config.WALLET_ADDRESS

infura_url = config.INFURA_URL

w3 = Web3(HTTPProvider(infura_url))

license_abi_json = json.loads(open('AMLicense_contract_abi.json', 'r').read())
project_abi_json = json.loads(open('AMProject_contract_abi.json', 'r').read())

AMLicense_contract = w3.eth.contract(address=AM_License_contract_address, abi=license_abi_json)
AMProject_contract = w3.eth.contract(address=AM_Project_contract_address, abi=project_abi_json)


def get_license_count():
    return AMLicense_contract.functions.getLicenseCount().call()


def get_license(_licenseid: int):
    return AMLicense_contract.functions.getLicense(_licenseid).call()


def get_print(_licenseid: int, _printid: int):
    return AMLicense_contract.functions.getPrint(_licenseid, _printid).call()


def add_license(_licensedby: str, _licensedto: str, _numprints: int, _parthash: str):

    nonce = w3.eth.getTransactionCount(wallet_address)
    txn_dict = AMLicense_contract.functions.addLicense(_licensedby, _licensedto, _numprints, _parthash).buildTransaction({
        'chainId': 3,
        'gas': 2000000,
        'gasPrice': w3.toWei('1', 'gwei'),
        'nonce': nonce,
    })

    signed_txn = w3.eth.account.signTransaction(txn_dict, private_key=wallet_private_key)

    result = w3.eth.sendRawTransaction(signed_txn.rawTransaction)

    tx_receipt = None

    count = 0
    while tx_receipt is None and (count < 30):
        try:
            time.sleep(10)

            tx_receipt = w3.eth.getTransactionReceipt(result)

            print(tx_receipt)
        except:
            tx_receipt = None
            count += 1


    if tx_receipt is None:
        return {'status': 'failed', 'error': 'timeout'}

    return {'status': 'added', 'transactionHash': tx_receipt['transactionHash'].hex()}


def add_print(_licenseid: int, _timestamp: int, _operatorid: int, _reporthash: str):

    nonce = w3.eth.getTransactionCount(wallet_address)
    txn_dict = AMLicense_contract.functions.addPrint(_licenseid, _timestamp, _operatorid, _reporthash).buildTransaction({
        'chainId': 3,
        'gas': 2000000,
        'gasPrice': w3.toWei('1', 'gwei'),
        'nonce': nonce,
    })

    signed_txn = w3.eth.account.signTransaction(txn_dict, private_key=wallet_private_key)

    result = w3.eth.sendRawTransaction(signed_txn.rawTransaction)

    tx_receipt = None

    count = 0
    while tx_receipt is None and (count < 30):
        try:
            time.sleep(10)

            tx_receipt = w3.eth.getTransactionReceipt(result)

            print(tx_receipt)
        except:
            tx_receipt = None
            count += 1


    if tx_receipt is None:
        return {'status': 'failed', 'error': 'timeout'}

    return {'status': 'added', 'transactionHash': tx_receipt['transactionHash'].hex()}


## AMProject.sol

def get_project_count():
    return AMProject_contract.functions.getProjectCount().call()


def get_project(_projectid: int):
    return AMProject_contract.functions.getProject(_projectid).call()


def get_hash(_projectid: int, _fileid: int):
    return AMProject_contract.functions.getHash(_projectid, _fileid).call()


def add_project(_author: str):

    nonce = w3.eth.getTransactionCount(wallet_address)
    txn_dict = AMProject_contract.functions.addProject(_author).buildTransaction({
        'chainId': 3,
        'gas': 2000000,
        'gasPrice': w3.toWei('1', 'gwei'),
        'nonce': nonce,
    })

    signed_txn = w3.eth.account.signTransaction(txn_dict, private_key=wallet_private_key)

    result = w3.eth.sendRawTransaction(signed_txn.rawTransaction)

    tx_receipt = None

    count = 0
    while tx_receipt is None and (count < 30):
        try:
            time.sleep(10)

            tx_receipt = w3.eth.getTransactionReceipt(result)

            print(tx_receipt)
        except:
            tx_receipt = None
            count += 1


    if tx_receipt is None:
        return {'status': 'failed', 'error': 'timeout'}

    return {'status': 'added', 'transactionHash': tx_receipt['transactionHash'].hex()}


def add_hash(_projectid: int, _checksum: str):

    nonce = w3.eth.getTransactionCount(wallet_address)
    txn_dict = AMProject_contract.functions.addHash(_projectid, _checksum).buildTransaction({
        'chainId': 3,
        'gas': 2000000,
        'gasPrice': w3.toWei('1', 'gwei'),
        'nonce': nonce,
    })

    signed_txn = w3.eth.account.signTransaction(txn_dict, private_key=wallet_private_key)

    result = w3.eth.sendRawTransaction(signed_txn.rawTransaction)

    tx_receipt = None

    count = 0
    while tx_receipt is None and (count < 30):
        try:
            time.sleep(10)

            tx_receipt = w3.eth.getTransactionReceipt(result)

            print(tx_receipt)
        except:
            tx_receipt = None
            count += 1


    if tx_receipt is None:
        return {'status': 'failed', 'error': 'timeout'}

    return {'status': 'added', 'transactionHash': tx_receipt['transactionHash'].hex()}
