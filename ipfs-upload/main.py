import os
from typing import Optional, List
import base64
from passlib.context import CryptContext
import json
from datetime import datetime, timedelta
import tempfile
from shutil import copyfile
import jwt
from jwt import PyJWTError

from pydantic import BaseModel
from flask import request

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
from starlette.responses import RedirectResponse, Response, JSONResponse, HTMLResponse
from starlette.requests import Request

from sqlalchemy import Table, Column, String, MetaData, create_engine
import database
import flow
import config
import logging
import ipfshttpclient
import tables
import encryption


# to get a string like this run:
# openssl rand -hex 32
SECRET_KEY = "043338707a1e2a947b937059d53ab9af5f8e1e0694bce51ab8c4dafacc7ffc8e"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# database
db = create_engine(config.DB_CONNECTION_STRING)
conn = db.connect()
users_table = tables.users_table(db)
projects_table = tables.projects_table(db)


# IPFS
client = ipfshttpclient.connect()


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
    user = database.get_user(users_table, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    return current_user


@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/loginv2", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/token", response_model=Token)
async def route_login_access_token(username: str = Form(...), password: str = Form(...)):
    user = database.authenticated(users_table, username, password)
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
async def new_user(username: str = Form(...), password: str = Form(...), name: str = Form(...)):
    try:
        database.add_user(users_table, username, password, name)
        return RedirectResponse("/login")
    except:
        return RedirectResponse(url="/")


@app.get("/signup/", response_class=HTMLResponse)
async def signup(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})


@app.get("/projects/{project_id}/view", response_class=HTMLResponse)
async def upload(project_id, request: Request):
    metadata = database.get_project_metadata(projects_table, project_id)
    action_url = "/projects/update/" + project_id
    return templates.TemplateResponse("upload.html", {"request": request, "metadata": metadata, "action_url": action_url})


@app.post("/projects/{project_id}/update", response_class=HTMLResponse)
async def view_project(project_id, request: Request):
    metadata = database.get_project_metadata(projects_table, project_id)
    action_url = "/projects/update/" + project_id
    return templates.TemplateResponse("upload.html", {"request": request, "metadata": metadata, "action_url": action_url})


@app.post("/projects/update/{project_id}")
async def import_file_post(project_id, files: Optional[UploadFile] = File(...), project_name: str = Form(...),
                           user_list: str = Form(...), data_type: str = Form(...)):
    if files.filename is not '':
        print(data_type)
        if data_type is 'none':
            print("error!")
            return {"Error": "You must specify a data type."}
        myFile = files.file
        encryptedFile = encryption.encrypt_file(myFile, config.CMK_ID)
        print('FILE ENCRYPTED? : ', encryptedFile)
        try:
            res = client.add(tempfile.gettempdir() + '/encrypted_file')
        except ipfshttpclient.exceptions.ConnectionError:
            return {"Error": "error adding file to IPFS"}
        fileHash = res['Hash']
        print(fileHash)
        from_path = '/ipfs/' + fileHash
        try:
            client.files.cp(from_path, '/'+files.filename+'.encrypted')
        except ipfshttpclient.exceptions.ErrorResponse:
            # file already exists
            pass
        files_dict = {
            "file_type": data_type,
            "filename": files.filename,
            "ipfs_hash": res['Hash']
        }

    else:
        files_dict = []
    metadata = {
        "project_name": project_name,
        "user_list": user_list,
        "files": files_dict,
        "last_updated": datetime.utcnow().isoformat()
    }
    # flow.updateProject(project_id, json.dumps(metadata))
    database.update_project(projects_table, project_id, metadata)
    return RedirectResponse("/projects/"+project_id+"/update")


@app.get("/projects")
async def list_my_projects(current_user: User = Depends(get_current_active_user)):
    return database.get_projects(projects_table, current_user['username'])


# @app.get("/projects/{projectId}")
# async def get_project_metadata(projectId):
#     return flow.getMetadata(projectId)


@app.post("/projects/{projectId}")
async def project_metadata(projectId):
    return flow.getMetadata(projectId)


@app.get("/projects/new")
async def new_project():
    flow.newProject()
    return RedirectResponse("/projects")


@app.get("/files/{ipfs_hash}")
async def download_and_decrypt(ipfs_hash):
    tempfilepath = tempfile.gettempdir() + '/amblockchainfiles'
    client.get(ipfs_hash, tempfilepath)
    tempfilepath = tempfile.gettempdir() + '/amblockchainfiles/' + ipfs_hash
    encryption.decrypt_file(tempfilepath)
    new_name = database.get_filename(projects_table, ipfs_hash)
    copyfile(tempfilepath + '.decrypted', 'F:/downloads/' + new_name)
    os.remove(tempfilepath + '.decrypted')