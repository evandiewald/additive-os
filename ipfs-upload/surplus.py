from fastapi import FastAPI, File, Form, UploadFile, Request, HTTPException, Depends, status, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import ipfshttpclient
import logging
import config
from sqlalchemy import Table, Column, String, MetaData, create_engine
import database
from pydantic import BaseModel
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from fastapi_sessions import SessionCookie, SessionInfo
from fastapi_sessions.backends import InMemoryBackend


# auth
SECRET_KEY = "043338707a1e2a947b937059d53ab9af5f8e1e0694bce51ab8c4dafacc7ffc8e "
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# FastAPI
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# IPFS
client = ipfshttpclient.connect()

# database
db = create_engine(config.DB_CONNECTION_STRING)
conn = db.connect()
users_table = Table('users', MetaData(db),
                    Column('username', String, primary_key=True, nullable=False),
                    Column('pwhash', String, nullable=False),
                    Column('name', String, nullable=False))





@app.post("/files")
async def import_file_post(email: str = Form(...), files: UploadFile = File(...)):
    logging.info('post files')
    myFile = files.file
    try:
        res = client.add(myFile)
    except ipfshttpclient.exceptions.ConnectionError:
        return {"Error": "error adding file to IPFS"}
    fileHash = res['Hash']
    print(email)
    from_path = '/ipfs/' + fileHash
    try:
        client.files.cp(from_path, '/'+files.filename)
    except ipfshttpclient.exceptions.ErrorResponse:
        # file already exists
        pass
    return {"filename": files.filename, "email": email}


# OAuth2
class User(BaseModel):
    username: str
    name: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class SessionData(BaseModel):
    username: str


test_session = SessionCookie(
    name="session",
    secret_key="helloworld",
    backend=InMemoryBackend(),
    data_model=SessionData,
    scheme_name="Test Cookies",
    auto_error=False
)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
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
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = database.get_user(users_table, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    return current_user


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


# @app.post("/token", response_model=Token)
# async def login_for_access_token(username: str = Form(...), password: str = Form(...)):
#     user = database.authenticated(users_table, username, password)
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Incorrect username or password",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
#     access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     access_token = create_access_token(
#         data={"sub": user['username']}, expires_delta=access_token_expires
#     )
#     return {"access_token": access_token, "token_type": "bearer"}

@app.post("/token")
async def login(username: str, response: Response, session_info: Optional[SessionInfo] = Depends(test_session)):
    old_session = None
    if session_info:
        old_session = session_info[0]

    test_user = SessionData(username=username)
    await test_session.create_session(test_user, response, old_session)
    return {"message": "You now have a session", "user": test_user}


@app.get("/users/me")
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user


# Routes
@app.get("/", response_class=HTMLResponse)
async def root(request: Request, session_data: Optional[SessionInfo] = Depends(test_session)):
    if session_data is None:
        raise HTTPException(
            status_code=403,
            detail="Not authenticated"
        )
    return templates.TemplateResponse("index.html", request)