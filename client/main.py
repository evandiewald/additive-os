import os
import random
from typing import Optional, List
import base64
from passlib.context import CryptContext
import json
from datetime import datetime, timedelta
import tempfile
from shutil import copyfile
import jwt
from jwt import PyJWTError
import boto3
import botocore
import requests
import ethereum
import time
import qrcode
from importer import BuildData
import ontology
import pytz
import urllib

from pydantic import BaseModel
import pymongo
from pycognito import Cognito

from fastapi import Depends, FastAPI, HTTPException, Form, File, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordRequestForm, OAuth2, HTTPBasic
from fastapi.security.base import SecurityBase
from fastapi.security.utils import get_authorization_scheme_param
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel
from fastapi.openapi.utils import get_openapi
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from starlette.status import HTTP_403_FORBIDDEN
from starlette.responses import RedirectResponse, Response, JSONResponse, HTMLResponse, FileResponse
from starlette.requests import Request

import database
import flow
import config
import logging
import ipfshttpclient
import tables
import encryption
import hashlib
from pinata import pin_to_pinata


# to get a string like this run:
# openssl rand -hex 32
SECRET_KEY = "043338707a1e2a947b937059d53ab9af5f8e1e0694bce51ab8c4dafacc7ffc8e"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# MongoDB
# mongo_client = pymongo.MongoClient(config.MONGO_CONNECTION_STRING)
# mongo_db = mongo_client.amblockchain


# IPFS
try:
    client = ipfshttpclient.connect()
except ipfshttpclient.exceptions.ConnectionError:
    print('No IPFS instance found. Running in remote mode.')


# get base credentials for access to cognito
payload = {}
files = {}
headers = {
  'x-api-key': config.CREDENTIALS_API_KEY
}

res = requests.request("GET", config.CREDENTIALS_API_URL, headers=headers, data=payload, files=files)
credentials = json.loads(res.json())['body']['Credentials']

session = boto3.Session(
    aws_access_key_id=credentials['AccessKeyId'],
    aws_secret_access_key=credentials['SecretAccessKey'],
    aws_session_token=credentials['SessionToken']
)

cognito_client = session.client('cognito-identity', region_name='us-east-1')


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str = None


class User(BaseModel):
    username: str
    name: str
    address: str
    AccessKeyId: str
    SecretKeyId: str
    SessionToken: str
    AccessToken: str


class UserInDB(User):
    hashed_password: str


class OAuth2PasswordBearerCookie(OAuth2):
    def __init__(
        self,
        tokenUrl: str,
        scheme_name: str = None,
        scopes: dict = None,
        auto_error: bool = True,
    ):
        if not scopes:
            scopes = {}
        flows = OAuthFlowsModel(password={"tokenUrl": tokenUrl, "scopes": scopes})
        super().__init__(flows=flows, scheme_name=scheme_name, auto_error=auto_error)

    async def __call__(self, request: Request) -> Optional[str]:
        header_authorization: str = request.headers.get("Authorization")
        cookie_authorization: str = request.cookies.get("Authorization")

        header_scheme, header_param = get_authorization_scheme_param(
            header_authorization
        )
        cookie_scheme, cookie_param = get_authorization_scheme_param(
            cookie_authorization
        )
        if header_scheme.lower() == "bearer":
            authorization = True
            scheme = header_scheme
            param = header_param

        elif cookie_scheme.lower() == "bearer":
            authorization = True
            scheme = cookie_scheme
            param = cookie_param

        else:
            authorization = False

        if not authorization or scheme.lower() != "bearer":
            if self.auto_error:
                raise HTTPException(
                    status_code=HTTP_403_FORBIDDEN, detail="Not authenticated"
                )
            else:
                return None
        return param


def garbage_collection():
    temp_path = tempfile.gettempdir() + '/amblockchainfiles'
    try:
        temp_files = os.listdir(temp_path)
        for file in temp_files:
            os.remove(temp_path+'/'+file)
    except FileNotFoundError:
        pass


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearerCookie(tokenUrl="/token")


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    # to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=HTTP_403_FORBIDDEN, detail="Could not validate credentials"
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except PyJWTError:
        raise credentials_exception
    auth_session = boto3.Session(
        aws_access_key_id=payload.get('AccessKeyId'),
        aws_secret_access_key=payload.get('SecretKey'),
        aws_session_token=payload.get('SessionToken')
    )
    u = Cognito(
        user_pool_id=config.USER_POOL_ID,
        client_id=config.USER_POOL_CLIENT,
        session=auth_session,
        access_token=payload.get('AccessToken'),
        username=username)
    user_obj = u.get_user()
    # user = {
    #     "username": user_obj.username,
    #     "address": user_obj.address,
    #     "name": user_obj.name,
    #     "AccessKeyId": payload.get("AccessKeyId"),
    #     "SecretKey": payload.get("SecretKey"),
    #     "SessionToken": payload.get("SessionToken"),
    #     "AccessToken": payload.get("AccessToken")
    # }
    user = User(
        username=user_obj.username,
        address=user_obj.address,
        name=user_obj.name,
        AccessKeyId=payload.get("AccessKeyId"),
        SecretKeyId=payload.get("SecretKey"),
        SessionToken=payload.get("SessionToken"),
        AccessToken=payload.get("AccessToken")
    )
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    return current_user


def mongo_db_auth(AccessKeyId, SecretKeyId, SessionToken):
    access_key_id = urllib.parse.quote_plus(AccessKeyId)
    secret_key_id = urllib.parse.quote_plus(SecretKeyId)
    session_token = urllib.parse.quote_plus(SessionToken)
    uri = f"mongodb+srv://{access_key_id}:" \
          f"{secret_key_id}@am-materials.xgcio.mongodb.net/?authMechanism=MONGODB-AWS&authSource=%24external" \
          f"&authMechanismProperties=AWS_SESSION_TOKEN:{session_token}"
    global mongo_client
    mongo_client = pymongo.MongoClient(uri)
    mongo_db = mongo_client.amblockchain
    return mongo_db


@app.route("/", methods=["GET", "POST"])
async def homepage(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/token")
async def token(username: str = Form(...), password: str = Form(...)):
    u = Cognito(
        user_pool_id=config.USER_POOL_ID,
        client_id=config.USER_POOL_CLIENT,
        session=session,
        username=username)
    u.authenticate(password=password)

    res = cognito_client.get_id(
        IdentityPoolId=config.IDENTITY_POOL_ID,
        Logins={
            config.IDENTITY_LOGIN: u.id_token
        }
    )
    credentials = cognito_client.get_credentials_for_identity(
        IdentityId=res['IdentityId'],
        Logins={
            config.IDENTITY_LOGIN: u.id_token
        }
    )

    data = {"sub": u.username,
            "AccessKeyId": credentials['Credentials']['AccessKeyId'],
            "SecretKey": credentials['Credentials']['SecretKey'],
            "SessionToken": credentials['Credentials']['SessionToken'],
            "AccessToken": u.access_token
            }
    access_token_expires = timedelta(minutes=60)
    access_token = create_access_token(data, expires_delta=access_token_expires)
    # token = access_token
    token = jsonable_encoder(access_token)
    response = RedirectResponse(url="/login_success")
    response.set_cookie(
        "Authorization",
        value=f"Bearer {token}",
        domain="localtest.me",
        httponly=True,
        max_age=3600,
        expires=3600,
        samesite='strict'
    )

    global mongo_db
    mongo_db = mongo_db_auth(data["AccessKeyId"], data["SecretKey"], data["SessionToken"])
    return response


@app.post("/login_success", response_class=HTMLResponse)
async def login_success(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/logout")
async def route_logout_and_remove_cookie():
    response = RedirectResponse(url="/")
    response.delete_cookie("Authorization", domain="localtest.me")
    try:
        mongo_client.close()
    except NameError:  # connection was never established in the first place
        pass
    return response


@app.get("/openapi.json")
async def get_open_api_endpoint():
    return JSONResponse(get_openapi(title="FastAPI", version='1.0.0', routes=app.routes))


@app.get("/docs")
async def get_documentation():
    return get_swagger_ui_html(openapi_url="/openapi.json", title="docs")


@app.get("/users/me/", response_class=User)
async def read_users_me(request: Request, current_user: User = Depends(get_current_active_user)):
    user_data = current_user.dict()
    return templates.TemplateResponse("user_data.html", {"request": request, "user_data": user_data})


@app.get("/users/me/items/")
async def read_own_items(current_user: User = Depends(get_current_active_user)):
    return [{"item_id": "Foo", "owner": current_user.username}]


@app.post("/newuser/")
async def new_user(request: Request, username: str = Form(...), password: str = Form(...), name: str = Form(...),
                   address: str = Form(...)):
    try:
        u = Cognito(
            user_pool_id=config.USER_POOL_ID,
            client_id=config.USER_POOL_CLIENT,
            session=session
        )
        u.set_base_attributes(email=username, name=name, address=address)
        u.register(username, password)
        return templates.TemplateResponse("validate_confirmation_code.html", {"request": request, "username": username})
    except:
        return JSONResponse({"Error": 400, "message": "User with this email address already exists. Please login or reset your password."})


@app.post("/validate")
async def confirm_code(username: str = Form(...), code: str = Form(...)):
    u = Cognito(
        user_pool_id=config.USER_POOL_ID,
        client_id=config.USER_POOL_CLIENT,
        session=session
    )
    u.confirm_sign_up(code, username)
    return RedirectResponse("/")


@app.get("/validate_form", response_class=HTMLResponse)
async def validate_form(request: Request, current_user: User = Depends(get_current_active_user)):
    print(current_user)
    return templates.TemplateResponse("validate_reset_code.html", {"request": request})


@app.get("/signup/", response_class=HTMLResponse)
async def signup(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})


@app.api_route("/projects/{project_id}/view", methods=["GET", "POST", "DELETE"])
async def upload(project_id, request: Request, current_user: User = Depends(get_current_active_user)):
    metadata, file_data = database.get_project_metadata_mongo(mongo_db, project_id)
    try:
        build_uid_list = database.get_build_trees(mongo_db, project_id)
    except IndexError:
        build_uid_list = []
    action_url = "/projects/update/" + project_id
    metadata_update_url = "/update/metadata/" + project_id
    download_urls = []
    for file in file_data:
        download_urls.append('/files/'+file['ipfs_hash'])
    fid_list = database.get_build_entries(mongo_db, {"project_id": project_id}, {"_id": 1})
    return templates.TemplateResponse("upload.html", {"request": request, "metadata": metadata, "file_data": file_data,
                                                      "action_url": action_url, "download_urls": download_urls, "build_uid_list": build_uid_list,
                                                      "metadata_update_url": metadata_update_url, "project_id": project_id, "fid_list": fid_list})


@app.get("/projects/{project_id}/blockchain", response_class=HTMLResponse)
async def view_blockchain_data(project_id, request: Request, current_user: User = Depends(get_current_active_user)):
    try:
        # blockchain_data = flow.getMetadata(project_id)
        blockchain_data = ethereum.get_project(int(project_id))
        metadata, file_list = database.get_project_metadata_mongo(mongo_db, project_id, active_only=False)
    except json.decoder.JSONDecodeError:
        blockchain_data = None
    return templates.TemplateResponse("blockchain.html", {"request": request, "blockchain_data": blockchain_data, "metadata": metadata, "files_list": file_list, "project_id": project_id})


@app.post("/projects/update/{project_id}")
async def import_file_post(request: Request, project_id, files: Optional[UploadFile] = File(...), data_type: str = Form(...),
                           remotepin: bool = Form(False), toblockchain: bool = Form(False), fid: Optional[str] = Form(None), current_user: User = Depends(get_current_active_user)):
    if files.filename is not '':
        print(data_type)
        if data_type is 'none':
            print("error!")
            return {"Error": "You must specify a data type."}

        # authenticated boto3 session
        auth_session = boto3.Session(
            aws_access_key_id=current_user.AccessKeyId,
            aws_secret_access_key=current_user.SecretKeyId,
            aws_session_token=current_user.SessionToken
        )

        myFile = files.file
        checksum = encryption.encrypt_file(myFile, config.CMK_ID, auth_session)
        print('FILE CHECKSUM : ', checksum)
        if remotepin is False:
            # try:
                res = client.add(tempfile.gettempdir() + '/encrypted_file')
                fileHash = res['Hash']
                print(fileHash)
            # except ipfshttpclient.exceptions.ConnectionError:
            #     res = pin_to_pinata(myFile, files.filename)
            #     fileHash = res['IpfsHash']
            #     print(fileHash)
                # return {"Error": "error adding file to IPFS"}
        else:
            # res = pin_to_pinata(myFile, files.filename)
            # fileHash = res['IpfsHash']
            # print(fileHash)
            raise({"UnimplementedFeatureError": "Remote pinning is not optimal yet."})

        from_path = '/ipfs/' + fileHash
        try:
            client.files.cp(from_path, '/'+files.filename+'.encrypted')
            client.pin.add(from_path, '/'+files.filename+'.encrypted')
        except ipfshttpclient.exceptions.ErrorResponse:
            # file already exists
            pass
        files_dict = {
            "project_id": project_id,
            "file_type": data_type,
            "filename": files.filename,
            "ipfs_hash": res['Hash'],
            "checksum": checksum,
            "FID": fid,
            "active": True
        }
        if fid != 'n/a':
            files_dict.update({"UID": fid + '.' + checksum[:6]})
        else:
            files_dict.update({"UID": ''})
        if data_type == 'spreadsheet':
            data_obj = BuildData(files.file, files.filename, project_id)
            build_entries_list = data_obj.entries
            build_data = data_obj.data
            database.add_build_data(mongo_db, build_data, build_entries_list)



    else:
        files_dict = []
    metadata = {
        # "_id": project_id,
        # "project_name": project_name,
        # "user_list": user_list,
        "last_updated": datetime.utcnow().isoformat()
    }
    # flow.updateProject(project_id, json.dumps(metadata))
    # database.update_project(projects_table, project_id, metadata)

    if files_dict:
        if toblockchain:
            # METAMASK
            txn_dict = ethereum.add_file(int(project_id), checksum)
            if fid:
                database.update_entry_files(mongo_db, fid, files_dict)
                database.update_tree_files(mongo_db, fid, files_dict)
            database.update_project_mongo(mongo_db, project_id, metadata, files_dict)
            return templates.TemplateResponse("sign_transaction.html", {"request": request, "contract_address":
                config.AMPROJECT_CONTRACT_ADDRESS, "txn_data": txn_dict['data'], "ipfs_hash": files_dict['ipfs_hash'],
                                                                        "checksum": files_dict['checksum'],
                                                                        "project_id": project_id, "action_url":
                                                                            '/add_hash_transaction/',
                                                                        "smart_contract_method": "AMProject.addFile"
                                                                        })
        else:
            files_dict['transaction_url'] = ''
        if fid:
            database.update_entry_files(mongo_db, fid, files_dict)
            database.update_tree_files(mongo_db, fid, files_dict)
    database.update_project_mongo(mongo_db, project_id, metadata, files_dict)

    return RedirectResponse("/projects/"+project_id+"/view")


@app.post("/update/metadata/{project_id}")
async def update_metadata(project_id, project_name: str = Form(...), user_list: Optional[str] = Form(None),
                          current_user: User = Depends(get_current_active_user)):
    metadata = {
        "_id": project_id,
        "project_name": project_name,
        "user_list": user_list,
        "last_updated": datetime.utcnow().isoformat()
    }
    files_dict = None
    database.update_project_mongo(mongo_db, project_id, metadata, files_dict)
    return RedirectResponse("/projects/"+project_id+"/view")


@app.get("/projects", response_class=HTMLResponse)
async def list_my_projects(request: Request, current_user: User = Depends(get_current_active_user)):
    project_list = database.get_projects_mongo(mongo_db, current_user.username)
    for project in project_list:
        try:
            d = datetime.fromisoformat(project['last_updated']).replace(tzinfo=pytz.utc)
            project['last_updated'] = d.astimezone(pytz.timezone('US/Eastern')).strftime('%d-%m-%Y %I:%M %p')
        except KeyError:
            project['last_updated'] = 'N/A'
    return templates.TemplateResponse("projects.html", {"request": request, "project_list": project_list})


@app.get("/projects/flow/new")
async def new_project(request: Request, current_user: User = Depends(get_current_active_user)):
    res = ethereum.add_project(current_user.address)
    return templates.TemplateResponse("sign_transaction.html", {"request": request, "contract_address":
        config.AMPROJECT_CONTRACT_ADDRESS, "txn_data": res['data'], "action_url": '/new_project_transaction/',
                                                                        "smart_contract_method":
                                                                            "AMProject.addProject"})


@app.post("/new_project_transaction")
async def new_project_transaction(txn_hash: str = Form(...), current_user: User = Depends(get_current_active_user)):
    transaction_url = 'https://ropsten.etherscan.io/tx/' + txn_hash
    new_project_id = database.init_project(mongo_db, current_user.username, transaction_url)
    return RedirectResponse("/projects/"+new_project_id+"/view")


@app.get("/files/{ipfs_hash}")
async def download_and_decrypt(ipfs_hash, current_user: User = Depends(get_current_active_user)):
    new_name = database.get_filename_mongo(mongo_db, ipfs_hash)
    # try:
    tempfilepath = tempfile.gettempdir() + '/amblockchainfiles'
    client.get(ipfs_hash, tempfilepath)
    tempfilepath = tempfile.gettempdir() + '/amblockchainfiles/' + ipfs_hash

    # authenticated boto3 session
    auth_session = boto3.Session(
        aws_access_key_id=current_user.AccessKeyId,
        aws_secret_access_key=current_user.SecretKeyId,
        aws_session_token=current_user.SessionToken
    )

    encryption.decrypt_file(tempfilepath, auth_session)

    copyfile(tempfilepath + '.decrypted', config.DOWNLOADS_FOLDER + new_name)
    return RedirectResponse('/projects')


@app.get("/files/{ipfs_hash}/delete")
async def delete_file(ipfs_hash):
    # database
    project_id, filename = database.delete_file(mongo_db, ipfs_hash)
    # ipfs
    try:
        client.files.rm('/'+filename+'.encrypted')
    except ipfshttpclient.exceptions.ErrorResponse:
        pass
    return RedirectResponse("/projects/"+project_id+"/view")


@app.get("/projects/{project_id}/user/{user}/remove")
async def remove_user(project_id, user, current_user: User = Depends(get_current_active_user)):
    database.remove_user(mongo_db, project_id, user)
    return RedirectResponse("/projects/" + project_id + "/view")


@app.post("/checksum/validate")
async def generate_checksum(files: Optional[UploadFile] = File(...)):
    file_hash = hashlib.sha3_224(files.file.read()).hexdigest()
    print(file_hash)
    return JSONResponse({"checksum": file_hash})


@app.route("/checksum", methods=["GET", "POST"])
async def checksum_upload(request: Request):
    return templates.TemplateResponse("checkhash.html", {"request": request})


@app.get("/reset_password", response_class=HTMLResponse)
async def reset_password_page(request: Request):
    return templates.TemplateResponse("reset_password.html", {"request": request})


@app.post("/reset_password/reset")
async def send_reset_code(request: Request, username: str = Form(...)):
    u = Cognito(
        user_pool_id=config.USER_POOL_ID,
        client_id=config.USER_POOL_CLIENT,
        session=session,
        username=username)
    u.initiate_forgot_password()

    return templates.TemplateResponse("validate_reset_code.html", {"request": request, "username": username})


@app.post("/reset_password/verify")
async def enter_reset_code(request: Request, new_password: str = Form(...), code: str = Form(...), username: str = Form(...)):
    u = Cognito(
        user_pool_id=config.USER_POOL_ID,
        client_id=config.USER_POOL_CLIENT,
        session=session,
        username=username)
    u.confirm_forgot_password(code, password=new_password)

    return RedirectResponse("/")


@app.route("/licenses", methods=["GET", "POST"])
async def view_licenses(request: Request, current_user: User = Depends(get_current_active_user)):
    license_list = database.get_licenses(mongo_db)
    return templates.TemplateResponse("licenses.html", {"request": request, "license_list": license_list})


@app.get("/licenses/{license_id}/new_print", response_class=HTMLResponse)
async def new_print_form(request: Request, license_id):
    return templates.TemplateResponse("new_print.html", {"request": request, "license_id": license_id})


@app.get("/licenses/new", response_class=HTMLResponse)
async def new_print_form(request: Request, current_user: User = Depends(get_current_active_user)):
    return templates.TemplateResponse("new_license.html", {"request": request, "username": current_user.username,
                                                           "address": current_user.address})


@app.post("/licenses/new/post")
async def new_license(request: Request, licensed_by_address: str = Form(...), licensed_to_address: str = Form(...), numprints: str = Form(...),
                      files: UploadFile = File(...), current_user: User = Depends(get_current_active_user), licensed_to_email: str = Form(...)):
    licensed_by_email = current_user.username
    parthash = hashlib.sha3_224(files.file.read()).hexdigest()

    txn_dict = ethereum.add_license(licensed_to_address, int(numprints), parthash)
    new_license_dict = {
        "licensed_by_address": licensed_by_address,
        "licensed_to_address": licensed_to_address,
        "numprints": numprints,
        "parthash": parthash,
        "licensed_to_email": licensed_to_email,
        "licensed_by_email": licensed_by_email
    }
    return templates.TemplateResponse("sign_transaction.html", {"request": request, "contract_address":
        config.AMLICENSE_CONTRACT_ADDRESS, "txn_data": txn_dict['data'], "new_license_dict": new_license_dict,
                                                                "action_url": "/new_license_transaction/",
                                                                        "smart_contract_method":
                                                                    "AMLicense.add_license"})


@app.post("/new_license_transaction")
async def new_license_transaction(txn_hash: str = Form(...), numprints: str = Form(...), parthash: str = Form(...),
                                  licensed_by_email: str = Form(...), licensed_to_email: str = Form(...),
                                  licensed_by_address: str = Form(...), licensed_to_address: str = Form(...),
                                  current_user: User = Depends(get_current_active_user)):
    transaction_url = 'https://ropsten.etherscan.io/tx/' + txn_hash
    timer = 0
    while timer < 10:
        if ethereum.get_license_count() > 0:
            try:
                license_id = ethereum.get_license_count() - 1
                database.add_license(mongo_db, license_id, transaction_url, int(numprints), parthash,
                                     licensed_by_email, licensed_to_email, licensed_by_address,
                                     licensed_to_address)
                return RedirectResponse("/licenses")
            except pymongo.errors.DuplicateKeyError:
                timer += 1
                time.sleep(3)
        else:
            timer += 1
            time.sleep(3)
    return {"message": "New License transaction timed out. Try a higher gas limit."}


@app.post("/licenses/{license_id}/new_print/post")
async def new_print(request: Request, license_id, files: UploadFile = File(...)):
    reporthash = hashlib.sha3_224(files.file.read()).hexdigest()
    ts = time.mktime(datetime.now().timetuple())
    txn_dict = ethereum.add_print(int(license_id), reporthash)
    return templates.TemplateResponse("sign_transaction.html", {"request": request, "txn_data": txn_dict['data'],
                                                                "contract_address": config.AMLICENSE_CONTRACT_ADDRESS,
                                                                "license_id": license_id,
                                                                "reporthash": reporthash, "action_url":
                                                                    "/new_print_transaction", "ts": str(ts),
                                                                        "smart_contract_method": "AMLicense.add_print"})


@app.post("/new_print_transaction")
async def new_print_transaction(txn_hash: str = Form(...), license_id: str = Form(...),
                                reporthash: str = Form(...), current_user: User = Depends(get_current_active_user)):
    transaction_url = 'https://ropsten.etherscan.io/tx/' + txn_hash
    database.add_print(mongo_db, int(license_id), current_user.address, reporthash, transaction_url)
    return RedirectResponse("/licenses")


@app.get("/licenses/{license_id}/prints/{print_id}")
async def view_print_license_info(request: Request, license_id, print_id, current_user: User = Depends(get_current_active_user)):
    license = database.get_print(mongo_db, int(license_id), int(print_id))
    return templates.TemplateResponse("printdata.html", {"request": request, "license": license, "license_id": license_id, "print_id": print_id})


@app.get("/licenses/{license_id}/prints/{print_id}/qr")
async def download_qr(request: Request, license_id, print_id):
    tempfilepath = tempfile.gettempdir() + '/amblockchainfiles/qr.png'

    # url = config.BASE_URL + "licenses/" + license_id + "/prints/" + print_id
    url = config.LICENSE_URL + "licenses/" + license_id + "/prints/" + print_id
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill='black', back_color='white')
    img.save(tempfilepath)
    return FileResponse(tempfilepath, media_type='application/octet-stream', filename='license_' + license_id + "_print_" + print_id + '.png')


@app.post("/entries/post")
async def query_entries(request: Request, query_dict: Optional[str] = Form(None), output_dict: Optional[str] = Form(None),
                        current_user: User = Depends(get_current_active_user)):
    try:
        query = json.loads(query_dict)
    except TypeError:
        query = None
    try:
        output = json.loads(output_dict)
    except TypeError:
        output = None
    entries_list = database.get_build_entries(mongo_db, query, output)
    return templates.TemplateResponse("entries.html", {"request": request, "entries_list": entries_list})
    # return RedirectResponse("/entries/"+str(query_dict)+'/'+str(output_dict))


@app.route("/entries/{query}/{output}", methods=["GET", "POST"])
async def view_entries(request: Request, query, output, current_user: User = Depends(get_current_active_user)):
    try:
        entries_list = database.get_build_entries(mongo_db, json.loads(query), json.loads(output))
    except KeyError:
        entries_list = database.get_build_entries(mongo_db, query, output)
    return templates.TemplateResponse("entries.html", {"request": request, "entries_list": entries_list})


@app.get("/entries/", response_class=HTMLResponse)
async def entries_form(request: Request):
    return templates.TemplateResponse("entries.html", {"request": request})


@app.get("/graphs/{project_id}/{tree_idx}", response_class=HTMLResponse)
async def create_graph(request: Request, project_id, tree_idx, current_user: User = Depends(get_current_active_user)):
    ontology.visualize_tree(mongo_db, project_id, int(tree_idx))
    return templates.TemplateResponse("graph.html", {"request": request})


@app.post("/outputs/{project_id}")
async def update_output(project_id, output_uid: str = Form(...), output_type: str = Form(...), output_value: str = Form(...),
                        current_user: User = Depends(get_current_active_user)):
    database.update_entry_output(mongo_db, output_uid, output_type, output_value)
    database.update_tree_output(mongo_db, output_uid, output_type, output_value)
    return RedirectResponse("/projects/" + project_id + "/view")


@app.post("/postprocess/{project_id}")
async def update_postprocessing(project_id, postprocess_uid: str = Form(...), postprocess_type: str = Form(...),
                                postprocess_value: str = Form(...), current_user: User = Depends(get_current_active_user)):
    database.update_entry_output(mongo_db, postprocess_uid, postprocess_type, postprocess_value)
    database.update_tree_output(mongo_db, postprocess_uid, postprocess_type, postprocess_value)
    return RedirectResponse("/projects/" + project_id + "/view")


@app.post("/add_hash_transaction")
async def add_hash_transaction(txn_hash: str = Form(...), ipfs_hash: str = Form(...), project_id: str = Form(...),
                               current_user: User = Depends(get_current_active_user)):
    transaction_url = 'https://ropsten.etherscan.io/tx/' + txn_hash
    database.add_transaction_to_file(mongo_db, ipfs_hash, transaction_url)
    return RedirectResponse("/projects/"+project_id+"/view")


@app.post("/users/me/update", response_model=User)
async def update_user(request: Request, name: str = Form(...), address: str = Form(...), current_user: User = Depends(get_current_active_user)):
    auth_session = boto3.Session(
        aws_access_key_id=current_user.AccessKeyId,
        aws_secret_access_key=current_user.SecretKeyId,
        aws_session_token=current_user.SessionToken
    )
    u = Cognito(
        user_pool_id=config.USER_POOL_ID,
        client_id=config.USER_POOL_CLIENT,
        session=auth_session,
        access_token=current_user.AccessToken,
        username=current_user.username)
    u.update_profile({'name': name, 'address': address}, attr_map=dict())
    user_data = u.get_user(attr_map=dict())
    return templates.TemplateResponse("user_data.html", {"request": request, "user_data": user_data})

