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

try:
    license_abi_json = json.loads(open('AMLicense_contract_abi.json', 'r').read())
    project_abi_json = json.loads(open('AMProject_contract_abi.json', 'r').read())

    AMLicense_contract = w3.eth.contract(address=AM_License_contract_address, abi=license_abi_json)
    AMProject_contract = w3.eth.contract(address=AM_Project_contract_address, abi=project_abi_json)
except:
    print('No contract ABI files found.')


def get_license_count():
    """Utility stored in the AMLicense smart contract to get current number of licenses.

    This may be useful for getting the index/license_id of the next license or for looping through all active licenses.

    Returns:
        The current number of licenses, or more specifically, the length of the licenses array.
    """
    return AMLicense_contract.functions.getLicenseCount().call()


def get_license(_licenseid: int):
    """Read-only function in AMLicense smart contract to get a license's details.

    As specified in AMLicense.sol, the License object contains the following:
    struct License {
        address licensedby;
        address licensedto;
        uint numprints;
        string parthash;
        Print[] prints;
    }

    Args:
        _licenseid: The uint index of the License of interest.

    Returns:
        A tuple containing the License details.
    """
    return AMLicense_contract.functions.getLicense(_licenseid).call()


def get_print(_licenseid: int, _printid: int):
    """Read-only function in the AMLicense contract to get a License.Print's details.

    Print objects are stored as an array within a License object. They store the following:
    struct Print {
        uint timestamp;
        uint operatorid;
        string reporthash;
    }

    Args:
        _licenseid: The uint license_id index of the License that stores this Print
        _printid: The uint index of the Print stored in the prints[] array

    Returns:
        A tuple containing the Print details of the form (timestamp, operatorid, reporthash).
    """
    return AMLicense_contract.functions.getPrint(_licenseid, _printid).call()


def add_license(_licensedby: str, _licensedto: str, _numprints: int, _parthash: str):
    """Function in the AMLicense contract to initiate a new license.

    As a transaction, this function requires gas fees. You may need to adjust the gas limit in the txn_dict line below
    if transactions are not going through. Should eventually be optimized to occur asynchronously (e.g. with a message
    queue, as it can often take 30-60s for transactions to execute.

    Args:
        _licensedby: The ETH wallet address of the one creating the license (e.g. the designer).
        _licensedto: The ETH wallet address of the one receiving the license (e.g. the fabrication shop)

    Returns:
        If successful, a dict containing the transactionHash. Otherwise, a timeout error.
    """
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
    """Function in the AMLicense contract to log a new print within a certain license.

    As a transaction, this function requires gas fees. You may need to adjust the gas limit in the txn_dict line below
    if transactions are not going through. This transaction will also fail if the number of allocated licenses (numprints)
    has already been met.

    Args:
        _licenseid: The license_id index of the license to which the print should be attached.
        _timestamp: A timestamp of when the print occurred (different from when this transaction occurred).
        _operatorid: An index that maps to a machine operator.
        _reporthash: The MD5 checksum of the build report.

    Returns:
        If successful, a dict containing the transactionHash. Otherwise, a timeout error.
    """
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
    """Utility stored in the AMProject smart contract to get current number of projects.

    This may be useful for getting the index/project_id of the next project or for looping through all active projects.

    Returns:
        The current number of projects, or more specifically, the length of the projects array
    """
    return AMProject_contract.functions.getProjectCount().call()


def get_project(_projectid: int):
    """Read-only function in AMProject smart contract to get a project's details.

    As specified in AMProject.sol, the Project object contains the following:
    struct Project {
        address author;
        string[] files;
    }

    Args:
        _projectid: The uint index of the Project of interest.

    Returns:
        A tuple containing the project details of the form (author, [files]).
    """
    return AMProject_contract.functions.getProject(_projectid).call()


def get_hash(_projectid: int, _fileid: int):
    """Read-only function in the AMProject contract to get a Project.file hash.

    Each Project contains a string[] array of checksums corresponding to authenticated project files.

    Args:
        _projectid: The uint project_id index of the Project that stores this file.
        _fileid: The uint index of the hash stored in the files[] array.

    Returns:
        The file hash.
    """
    return AMProject_contract.functions.getHash(_projectid, _fileid).call()


def add_project(_author: str):
    """Function in the AMProject contract to initiate a new Project.

    When initializing a project, you only need to specify the _author. The files[] array will initialize as empty.
    As a transaction, this function requires gas fees. You may need to adjust the gas limit in the txn_dict line below
    if transactions are not going through. Should eventually be optimized to occur asynchronously (e.g. with a message
    queue, as it can often take 30-60s for transactions to execute.

    Args:
        _author: The ETH wallet address of the project author.

    Returns:
        If successful, a dict containing the transactionHash. Otherwise, a timeout error.
    """
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
    """Function in the AMProject contract to associate a verified file hash with a Project.

    As a transaction, this function requires gas fees. You may need to adjust the gas limit in the txn_dict line below
    if transactions are not going through. Should eventually be optimized to occur asynchronously (e.g. with a message
    queue, as it can often take 30-60s for transactions to execute.

    Args:
        _projectid: The project_id index of the Project to associate the file with.
        _checksum: The MD5 checksum of the verified file.

    Returns:
        If successful, a dict containing the transactionHash. Otherwise, a timeout error.
    """
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
