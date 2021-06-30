import database
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
from starlette.requests import Request
import pymongo
import config


# MongoDB
mongo_client = pymongo.MongoClient(config.MONGO_CONNECTION_STRING)
mongo_db = mongo_client.amblockchain


app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/")
async def homepage(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/licenses/{license_id}/prints/{print_id}")
async def view_print_license_info(request: Request, license_id, print_id):
    license = database.get_print(mongo_db, int(license_id), int(print_id))
    return templates.TemplateResponse("printdata.html", {"request": request, "license": license, "license_id": license_id, "print_id": print_id})