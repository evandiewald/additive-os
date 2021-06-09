import pymongo
import config
import ipfshttpclient


# for sync_pins.py daemon
def get_pins_list(mongo_db):
    files = mongo_db['files']
    file_data = files.find({}, {"ipfs_hash": 1})
    pins_list = []
    for file in file_data:
        pins_list.append(file['ipfs_hash'])
    return pins_list


# MongoDB
mongo_client = pymongo.MongoClient(config.MONGO_CONNECTION_STRING)
mongo_db = mongo_client.amblockchain


pins_list = get_pins_list(mongo_db)

for pin in pins_list:
    with ipfshttpclient.connect() as client:
        try:
            res = client.pin.ls(pin)
            print('Already have a pin for hash ', pin)
        except ipfshttpclient.exceptions.ErrorResponse:
            get_res = client.get(pin)
            pin_res = client.pin.add(pin)
            print('Added pin for hash ', pin)


