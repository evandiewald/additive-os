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
import requests
import ethereum
import time
import qrcode
from importer import BuildData
import ontology
import pytz

from pydantic import BaseModel
import pymongo

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

from sqlalchemy import Table, Column, String, MetaData, create_engine
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

# Postgres
db = create_engine(config.DB_CONNECTION_STRING)
conn = db.connect()
users_table = tables.users_table(db)
projects_table = tables.projects_table(db)

# MongoDB
mongo_client = pymongo.MongoClient(config.MONGO_CONNECTION_STRING)
mongo_db = mongo_client.amblockchain

# IPFS
try:
    client = ipfshttpclient.connect()
except ipfshttpclient.exceptions.ConnectionError:
    print('No IPFS instance found. Running in remote mode.')


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str = None


class User(BaseModel):
    username: str
    name: str


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


class BasicAuth(SecurityBase):
    def __init__(self, scheme_name: str = None, auto_error: bool = True):
        self.scheme_name = scheme_name or self.__class__.__name__
        self.auto_error = auto_error
        self.model = SecurityBase()

    async def __call__(self, request: Request) -> Optional[str]:
        authorization: str = request.headers.get("Authorization")
        scheme, param = get_authorization_scheme_param(authorization)
        if not authorization or scheme.lower() != "basic":
            if self.auto_error:
                raise HTTPException(
                    status_code=HTTP_403_FORBIDDEN, detail="Not authenticated"
                )
            else:
                return None
        return param


# basic_auth = BasicAuth(auto_error=True)
basic_auth = HTTPBasic()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearerCookie(tokenUrl="/token")


def create_access_token(*, data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
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
    # user = database.get_user(users_table, username=token_data.username)
    user = database.get_user(mongo_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    return current_user


@app.route("/", methods=["GET", "POST"])
async def homepage(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/loginv2", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/token", response_model=Token)
async def route_login_access_token(username: str = Form(...), password: str = Form(...)):
    # user = database.authenticated(users_table, username, password)

    user = database.authenticated(mongo_db, username, password)
    if not user:
        RedirectResponse(url="/signup")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user['username']}, expires_delta=access_token_expires
    )
    token = jsonable_encoder(access_token)

    response = RedirectResponse(url="/login_success")
    response.set_cookie(
        "Authorization",
        value=f"Bearer {token}",
        domain="localtest.me",
        httponly=True,
        max_age=1800,
        expires=1800,
        samesite='strict'
    )
    return response


@app.post("/login_success", response_class=HTMLResponse)
async def login_success(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/logout")
async def route_logout_and_remove_cookie():
    response = RedirectResponse(url="/")
    response.delete_cookie("Authorization", domain="localtest.me")
    return response


@app.get("/login")
async def login_basic(auth: BasicAuth = Depends(basic_auth)):
    if not auth:
        response = Response(headers={"WWW-Authenticate": "Basic"}, status_code=401)
        return response

    try:
        decoded = base64.b64decode(auth).decode("ascii")
        username, _, password = decoded.partition(":")
        user = database.authenticated(users_table, username, password)
        if not user:
            raise HTTPException(status_code=400, detail="Incorrect email or password. New User? Sign up at http:localtest.me:8000/signup")

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": username}, expires_delta=access_token_expires
        )

        token = jsonable_encoder(access_token)

        response = RedirectResponse(url="/")
        response.set_cookie(
            "Authorization",
            value=f"Bearer {token}",
            domain="localtest.me",
            httponly=True,
            max_age=1800,
            expires=1800,
            samesite='strict'
        )
        return response

    except:
        response = Response(headers={"WWW-Authenticate": "Basic"}, status_code=401)
        return response


@app.get("/openapi.json")
async def get_open_api_endpoint():
    return JSONResponse(get_openapi(title="FastAPI", version='1.0.0', routes=app.routes))


@app.get("/docs")
async def get_documentation():
    return get_swagger_ui_html(openapi_url="/openapi.json", title="docs")


@app.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@app.get("/users/me/items/")
async def read_own_items(current_user: User = Depends(get_current_active_user)):
    return [{"item_id": "Foo", "owner": current_user['username']}]


@app.post("/newuser/")
async def new_user(username: str = Form(...), password: str = Form(...), name: str = Form(...), address: str = Form(...)):
    try:
        # database.add_user(users_table, username, password, name)
        database.add_user(mongo_db, username, password, name, address)
        return RedirectResponse("/loginv2")
    except:
        return JSONResponse({"Error": 400, "message": "User with this email address already exists. Please login or reset your password."})


@app.get("/signup/", response_class=HTMLResponse)
async def signup(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})


# @app.get("/projects/{project_id}/view", response_class=HTMLResponse)
@app.api_route("/projects/{project_id}/view", methods=["GET", "POST", "DELETE"])
async def upload(project_id, request: Request, current_user: User = Depends(get_current_active_user)):
    # metadata = database.get_project_metadata(projects_table, project_id)

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
async def view_blockchain_data(project_id, request: Request):
    try:
        # blockchain_data = flow.getMetadata(project_id)
        blockchain_data = ethereum.get_project(int(project_id))
        print(blockchain_data)
        metadata, file_list = database.get_project_metadata_mongo(mongo_db, project_id, active_only=False)
    except json.decoder.JSONDecodeError:
        blockchain_data = None
    return templates.TemplateResponse("blockchain.html", {"request": request, "blockchain_data": blockchain_data, "metadata": metadata, "files_list": file_list, "project_id": project_id})


@app.post("/projects/{project_id}/update", response_class=HTMLResponse)
async def view_project(project_id, request: Request):
    metadata = database.get_project_metadata(projects_table, project_id)
    action_url = "/projects/update/" + project_id
    return templates.TemplateResponse("upload.html", {"request": request, "metadata": metadata, "action_url": action_url})


@app.post("/projects/update/{project_id}")
async def import_file_post(project_id, files: Optional[UploadFile] = File(...), data_type: str = Form(...),
                           remotepin: bool = Form(False), toblockchain: bool = Form(False), fid: Optional[str] = Form(None), current_user: User = Depends(get_current_active_user)):
    if files.filename is not '':
        print(data_type)
        if data_type is 'none':
            print("error!")
            return {"Error": "You must specify a data type."}

        myFile = files.file
        checksum = encryption.encrypt_file(myFile, config.CMK_ID)
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
            # files_data = database.get_data_for_flow(mongo_db, project_id)
            # flow.updateProject(project_id, str(files_data))
            res = ethereum.add_hash(int(project_id), checksum)
            transaction_url = 'https://ropsten.etherscan.io/tx/' + res['transactionHash']
            files_dict['transaction_url'] = transaction_url
        else:
            files_dict['transaction_url'] = ''
        if fid:
            database.update_entry_files(mongo_db, fid, files_dict)
            database.update_tree_files(mongo_db, fid, files_dict)
    database.update_project_mongo(mongo_db, project_id, metadata, files_dict)


    return RedirectResponse("/projects/"+project_id+"/view")


@app.post("/update/metadata/{project_id}")
async def update_metadata(project_id, project_name: str = Form(...), user_list: Optional[str] = Form(None)):
    print('got here')
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
    project_list = database.get_projects_mongo(mongo_db, current_user['username'])
    for project in project_list:
        d = datetime.fromisoformat(project['last_updated']).replace(tzinfo=pytz.utc)
        project['last_updated'] = d.astimezone(pytz.timezone('US/Eastern')).strftime('%d-%m-%Y %I:%M %p')
    return templates.TemplateResponse("projects.html", {"request": request, "project_list": project_list})


# @app.get("/projects/{projectId}")
# async def project_metadata(projectId):
#     # return flow.getMetadata(projectId)
#     return ethereum.get_project(int(projectId))


@app.get("/projects/flow/new")
async def new_project(current_user: User = Depends(get_current_active_user)):
    # flow.newProject()
    res = ethereum.add_project(current_user['address'])
    transaction_url = 'https://ropsten.etherscan.io/tx/' + res['transactionHash']
    new_project_id = database.init_project(mongo_db, current_user['username'], transaction_url)
    print("/projects/"+new_project_id+"/view")
    return RedirectResponse("/projects/"+new_project_id+"/view")


@app.get("/files/{ipfs_hash}")
async def download_and_decrypt(ipfs_hash):
    new_name = database.get_filename_mongo(mongo_db, ipfs_hash)
    # try:
    tempfilepath = tempfile.gettempdir() + '/amblockchainfiles'
    client.get(ipfs_hash, tempfilepath)
    tempfilepath = tempfile.gettempdir() + '/amblockchainfiles/' + ipfs_hash
    encryption.decrypt_file(tempfilepath)

    # except:
    #     res = requests.get('https://gateway.pinata.cloud/ipfs/' + ipfs_hash)
    #     tempfilepath = config.DOWNLOADS_FOLDER + ipfs_hash
    #     with open(tempfilepath, 'wb') as f:
    #         f.write(res['content'])
    #     print('File written')
    #     encryption.decrypt_file(tempfilepath)
    #     print('File decrypted')
    copyfile(tempfilepath + '.decrypted', config.DOWNLOADS_FOLDER + new_name)
    # dest = tempfile.gettempdir() + '/amblockchainfiles/' + new_name
    # os.remove(tempfilepath + '.decrypted')
    # return FileResponse(tempfilepath + '.decrypted', media_type='application/octet-stream', filename=new_name)
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
    # blockchain
    # files_data = database.get_data_for_flow(mongo_db, project_id)
    # flow.updateProject(project_id, str(files_data))
    return RedirectResponse("/projects/"+project_id+"/view")


@app.get("/projects/{project_id}/user/{user}/remove")
async def remove_user(project_id, user):
    database.remove_user(mongo_db, project_id, user)
    return RedirectResponse("/projects/" + project_id + "/view")


@app.post("/checksum/validate")
async def generate_checksum(files: Optional[UploadFile] = File(...)):
    file_hash = hashlib.md5(files.file.read()).hexdigest()
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
    reset_code = str(random.randrange(0, 999999)).zfill(6)
    code_hash = hashlib.sha256(bytes(reset_code, encoding='utf8')).hexdigest()
    expiration = datetime.now() + timedelta(minutes=5)
    email_template = """<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>AM Blockchain Password Reset</title>
        </head>
        <body>
        
        <p>Your password reset code is {}.</p>
        
        </body>
        </html>""".format(reset_code)

    ses_client = boto3.client('sesv2')
    response = ses_client.send_email(FromEmailAddress='do-not-reply@amrepository.com',
                                 FromEmailAddressIdentityArn='arn:aws:ses:us-east-1:668146110194:identity/amrepository.com',
                                 Destination={
                                     'ToAddresses': [username]
                                 },
                                 Content={
                                     'Simple': {
                                         'Subject': {
                                             'Data': 'Password reset requested for AM Blockchain'
                                         },
                                         'Body': {
                                             'Html': {
                                                 'Data': email_template
                                             }
                                         }
                                     }
                                 })
    return templates.TemplateResponse("validate_reset_code.html", {"request": request, "code_hash": code_hash, "expiration": expiration.isoformat(), "username": username})


@app.post("/reset_password/verify")
async def enter_reset_code(request: Request, code_hash: str = Form(...), expiration: str = Form(...), code: str = Form(...), username: str = Form(...)):
    submitted_code_hash = hashlib.sha256(bytes(code, encoding='utf8')).hexdigest()
    if datetime.now() > datetime.fromisoformat(expiration):
        return JSONResponse({"status": 400, "message": "Code expired"})
    elif submitted_code_hash != code_hash:
        return JSONResponse({"status": 400, "message": "Invalid code"})
    else:
        print('Success')
        return templates.TemplateResponse("update_password.html", {"request": request, "username": username})


@app.post("/update_password")
async def update_password(request: Request, username: str = Form(...), new_password: str = Form(...)):
    database.update_password(users_table, username, new_password)
    return templates.TemplateResponse("login.html", {"request": request})


@app.route("/licenses", methods=["GET", "POST"])
async def view_licenses(request: Request):
    license_list = database.get_licenses(mongo_db)
    return templates.TemplateResponse("licenses.html", {"request": request, "license_list": license_list})


@app.get("/licenses/{license_id}/new_print", response_class=HTMLResponse)
async def new_print_form(request: Request, license_id):
    return templates.TemplateResponse("new_print.html", {"request": request, "license_id": license_id})


@app.get("/licenses/new", response_class=HTMLResponse)
async def new_print_form(request: Request, current_user: User = Depends(get_current_active_user)):
    return templates.TemplateResponse("new_license.html", {"request": request, "username": current_user['username'], "address": current_user['address']})


@app.post("/licenses/new/post")
async def new_license(request: Request, licensed_by_address: str = Form(...), licensed_to_address: str = Form(...), numprints: str = Form(...),
                      files: UploadFile = File(...), current_user: User = Depends(get_current_active_user), licensed_to_email: str = Form(...)):
    licensed_by_email = current_user['username']
    parthash = hashlib.md5(files.file.read()).hexdigest()
    res = ethereum.add_license(licensed_by_address, licensed_to_address, int(numprints), parthash)
    transaction_hash = res['transactionHash']
    transaction_url = 'https://ropsten.etherscan.io/tx/' + transaction_hash
    license_id = ethereum.get_license_count() - 1
    database.add_license(mongo_db, license_id, transaction_url, int(numprints), parthash, licensed_by_email, licensed_to_email, licensed_by_address, licensed_to_address)
    return RedirectResponse("/licenses")


@app.post("/licenses/{license_id}/new_print/post")
async def new_print(request: Request, license_id, operatorid: str = Form(...), files: UploadFile = File(...)):
    reporthash = hashlib.md5(files.file.read()).hexdigest()
    ts = time.mktime(datetime.now().timetuple())
    res = ethereum.add_print(int(license_id), int(ts), int(operatorid), reporthash)
    transaction_hash = res['transactionHash']
    transaction_url = 'https://ropsten.etherscan.io/tx/' + transaction_hash
    database.add_print(mongo_db, int(license_id), ts, int(operatorid), reporthash, transaction_url)
    return RedirectResponse("/licenses")


@app.get("/licenses/{license_id}/prints/{print_id}")
async def view_print_license_info(request: Request, license_id, print_id):
    license = database.get_print(mongo_db, int(license_id), int(print_id))
    return templates.TemplateResponse("printdata.html", {"request": request, "license": license, "license_id": license_id, "print_id": print_id})


@app.get("/licenses/{license_id}/prints/{print_id}/qr")
async def download_qr(request: Request, license_id, print_id):
    tempfilepath = tempfile.gettempdir() + '/qr.png'

    # url = config.BASE_URL + "licenses/" + license_id + "/prints/" + print_id
    url = config.LICENSE_URL + "licenses/" + license_id + "/prints/" + print_id
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill='black', back_color='white')
    img.save(tempfilepath)
    return FileResponse(tempfilepath, media_type='application/octet-stream', filename='license_' + license_id + "_print_" + print_id + '.png')


@app.post("/entries/post")
async def query_entries(request: Request, query_dict: Optional[str] = Form(None), output_dict: Optional[str] = Form(None)):
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
async def view_entries(request: Request, query, output):
    try:
        entries_list = database.get_build_entries(mongo_db, json.loads(query), json.loads(output))
    except KeyError:
        entries_list = database.get_build_entries(mongo_db, query, output)
    return templates.TemplateResponse("entries.html", {"request": request, "entries_list": entries_list})


@app.get("/entries/", response_class=HTMLResponse)
async def entries_form(request: Request):
    return templates.TemplateResponse("entries.html", {"request": request})


@app.get("/graphs/{project_id}/{tree_idx}", response_class=HTMLResponse)
async def create_graph(request: Request, project_id, tree_idx):
    ontology.visualize_tree(mongo_db, project_id, int(tree_idx))
    return templates.TemplateResponse("graph.html", {"request": request})


@app.post("/outputs/{project_id}")
async def update_output(project_id, output_uid: str = Form(...), output_type: str = Form(...), output_value: str = Form(...)):
    database.update_entry_output(mongo_db, output_uid, output_type, output_value)
    database.update_tree_output(mongo_db, output_uid, output_type, output_value)
    return RedirectResponse("/projects/" + project_id + "/view")


@app.post("/postprocess/{project_id}")
async def update_postprocessing(project_id, postprocess_uid: str = Form(...), postprocess_type: str = Form(...), postprocess_value: str = Form(...)):
    database.update_entry_output(mongo_db, postprocess_uid, postprocess_type, postprocess_value)
    database.update_tree_output(mongo_db, postprocess_uid, postprocess_type, postprocess_value)
    return RedirectResponse("/projects/" + project_id + "/view")
