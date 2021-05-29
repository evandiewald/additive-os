import config
import psycopg2
import sqlalchemy
from sqlalchemy import Table, Column, String, MetaData, func
import hashlib
import json
import pymongo
import flow

## users table
def get_hash(hash_input: str):
    return hashlib.sha256(bytes(hash_input, 'utf-8')).hexdigest()


def add_user(users_table, username, raw_password, name):
    try:
        insert_statement = users_table.insert().values(username=username, pwhash=get_hash(raw_password), name=name)
        insert_statement.execute()
        return 'Success'
    except sqlalchemy.exc.IntegrityError:
        return {"UserExistsError": "User with this email already exists."}


def get_user(users_table, username):
    try:
        select_statement = users_table.select().where(users_table.columns.username==username)
        result = select_statement.execute().fetchone()
        user = {"username": result[0], "pwhash": result[1], "name": result[2]}
        return user
    except TypeError:
        return {"UserDoesNotExistError": "User with this email does not exist."}


def delete_user(users_table, username):
    delete_statement = users_table.delete().where(users_table.columns.username==username).execute()
    return True


def authenticated(users_table, username, password):
    user = get_user(users_table, username)
    if user['pwhash'] == get_hash(password):
        return user
    else:
        return False


def update_password(users_table, username, new_password):
    update_statement = users_table.update().where(users_table.columns.username==username).values(pwhash=get_hash(new_password)).execute()
    return True


## projects table
def update_project(projects_table, project_id, metadata):
    try:
        insert_statement = projects_table.insert().values(user_list=metadata['user_list'],
                                                          project_id=project_id,
                                                          project_name=metadata['project_name'],
                                                          files=json.dumps(metadata['files']),
                                                          last_updated=metadata['last_updated']).execute()
    except sqlalchemy.exc.IntegrityError:
        existing_info = projects_table.select().where(projects_table.columns.project_id == project_id).execute().fetchone()
        if not metadata['user_list']:
            metadata['user_list'] = existing_info[2]
        if not metadata['project_name']:
            metadata['project_name'] = existing_info[1]
        if existing_info[3] is not None:
            metadata['files'] = list(existing_info[3]).append(metadata['files'])
        print(metadata['user_list'])
        update_statement = projects_table.update().where(projects_table.columns.project_id == project_id).values(user_list=metadata['user_list'],
                                                                                                                 project_name=metadata['project_name'],
                                                                                                                 files=json.dumps(metadata['files']),
                                                                                                                 last_updated=metadata['last_updated']).execute()
        print('updated')
    return True


def update_project_mongo(mongo_db, project_id, metadata, files_dict):
    project_data = mongo_db['project-data']
    files = mongo_db['files']
    try:
        project_data.insert_one(metadata)
    except pymongo.errors.DuplicateKeyError:
        newname = { "$set": {"project_name": metadata['project_name'], "last_updated": metadata['last_updated']} }
        project_data.update_one({"_id": project_id}, newname)
        if metadata['user_list'] is not None:
            newuser = {"$push": {"user_list": metadata['user_list']}}
            project_data.update_one({"_id": project_id}, newuser)
    if files_dict:
        files.insert_one(files_dict)




def update_project_files(projects_table, project_id, metadata):
    existing_info = projects_table.select().where(projects_table.columns.project_id == project_id).execute().fetchone()
    if existing_info[3] is not None:
        metadata['files'] = [metadata['files'], existing_info[3]]
    update_statement = projects_table.update().where(projects_table.columns.project_id == project_id).values(files=metadata['files'],
                                                                                                             last_updated=metadata['last_updated']).execute()
    print('updated')
    return True


def get_projects(projects_table, email):
    email = '{' + email + '}'
    select_statement = sqlalchemy.select(projects_table).where(projects_table.columns.user_list.contains(email)).execute()
    return select_statement.fetchall()


def get_projects_mongo(mongo_db, email):
    projects = mongo_db['project-data']
    res = projects.find({'user_list': email})
    project_list = []
    for project in res:
        project_list.append(project)
    print(project_list)
    return project_list


def get_filename(projects_table, ipfs_hash):
    select_statement = sqlalchemy.select(projects_table).where(projects_table.columns.ipfs_hash == ipfs_hash).execute()
    res = select_statement.fetchone()
    return res[3]


def get_filename_mongo(mongo_db, ipfs_hash):
    files = mongo_db['files']
    filename = files.find_one({"ipfs_hash": ipfs_hash}, {"filename": 1})
    print(filename['filename'])
    return filename['filename']


def get_project_metadata(projects_table, project_id):
    select_statement = sqlalchemy.select(projects_table).where(projects_table.columns.project_id == project_id).execute()
    res = select_statement.fetchone()
    return res


def get_project_metadata_mongo(mongo_db, project_id):
    project_data = mongo_db['project-data']
    files = mongo_db['files']
    metadata = project_data.find_one({"_id": project_id})
    file_data = files.find({"project_id": project_id})
    file_list = []
    for file in file_data:
        file_list.append(file)
    print(metadata)
    print(file_data)
    return metadata, file_list


def get_data_for_flow(mongo_db, project_id):
    files = mongo_db['files']
    file_data = files.find({"project_id": project_id}, {"_id": 0, "project_id": 1, "filename": 1, "file_type": 1, "checksum": 1})
    file_list = []
    for file in file_data:
        file_list.append(file)
    return file_list


def delete_file(mongo_db, ipfs_hash):
    files = mongo_db['files']
    project_id = files.find_one({"ipfs_hash": ipfs_hash}, {"project_id": 1, "filename": 1})
    files.delete_one( {"ipfs_hash": ipfs_hash})
    return project_id['project_id'], project_id['filename']


def remove_user(mongo_db, project_id, user):
    project_data = mongo_db['project-data']
    query = { "$pull": { "user_list": user}}
    project_data.update_one({"_id": project_id}, query)


def init_project(mongo_db, user):
    project_data = mongo_db['project-data']
    init_project_id = str(max(flow.getProjects()['collection']))
    project_data.insert_one({"_id": init_project_id, "user_list": [user]})
    return init_project_id