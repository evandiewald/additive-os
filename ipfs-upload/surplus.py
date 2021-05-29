import config
import pymongo

client = pymongo.MongoClient(config.MONGO_CONNECTION_STRING)

db = client.amdb

build_data = db.build_data

print(build_data.find_one())