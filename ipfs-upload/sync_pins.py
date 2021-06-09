from database import get_pins_list
import pymongo
import config
import ipfshttpclient


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
            res = client.pin.add(pin)
            print('Added pin for hash ', pin)


