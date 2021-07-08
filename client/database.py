import config
import hashlib
import json
import pymongo
import flow
import datetime
import ethereum
import time


## users table
def get_hash(hash_input: str):
    return hashlib.sha256(bytes(hash_input, 'utf-8')).hexdigest()


# def add_user(users_table, username, raw_password, name):
#     try:
#         insert_statement = users_table.insert().values(username=username, pwhash=get_hash(raw_password), name=name)
#         insert_statement.execute()
#         return 'Success'
#     except sqlalchemy.exc.IntegrityError:
#         return {"UserExistsError": "User with this email already exists."}
def add_user(mongo_db, username, raw_password, name, address):
    users = mongo_db['users']
    new_user = {"_id": username, "username": username, "pwhash": get_hash(raw_password), "name": name, "address": address}
    # try:
    users.insert_one(new_user)
    # except:
    return 'Success'



# def get_user(users_table, username):
#     try:
#         select_statement = users_table.select().where(users_table.columns.username==username)
#         result = select_statement.execute().fetchone()
#         user = {"username": result[0], "pwhash": result[1], "name": result[2]}
#         return user
#     except TypeError:
#         return {"UserDoesNotExistError": "User with this email does not exist."}

def get_user(mongo_db, username):
    users = mongo_db['users']
    user = users.find_one({"username": username})
    return user


# def delete_user(users_table, username):
#     delete_statement = users_table.delete().where(users_table.columns.username==username).execute()
#     return True
def delete_user(mongo_db, username):
    users = mongo_db['users']
    users.delete_one({"username": username})
    return True


# def authenticated(users_table, username, password):
#     user = get_user(users_table, username)
#     if user['pwhash'] == get_hash(password):
#         return user
#     else:
#         return False

def authenticated(mongo_db, username, password):
    user = get_user(mongo_db, username)
    if user['pwhash'] == get_hash(password):
        return user
    else:
        return False


# def update_password(users_table, username, new_password):
#     update_statement = users_table.update().where(users_table.columns.username==username).values(pwhash=get_hash(new_password)).execute()
#     return True
def update_password(mongo_db, username, new_password):
    users = mongo_db['users']
    query = {"username": username}
    newvalues = {"$set": {"pwhash": get_hash(new_password)} }
    users.update_one(query, newvalues)
    return True



## projects table
# def update_project(projects_table, project_id, metadata):
#     try:
#         insert_statement = projects_table.insert().values(user_list=metadata['user_list'],
#                                                           project_id=project_id,
#                                                           project_name=metadata['project_name'],
#                                                           files=json.dumps(metadata['files']),
#                                                           last_updated=metadata['last_updated']).execute()
#     except sqlalchemy.exc.IntegrityError:
#         existing_info = projects_table.select().where(projects_table.columns.project_id == project_id).execute().fetchone()
#         if not metadata['user_list']:
#             metadata['user_list'] = existing_info[2]
#         if not metadata['project_name']:
#             metadata['project_name'] = existing_info[1]
#         if existing_info[3] is not None:
#             metadata['files'] = list(existing_info[3]).append(metadata['files'])
#         print(metadata['user_list'])
#         update_statement = projects_table.update().where(projects_table.columns.project_id == project_id).values(user_list=metadata['user_list'],
#                                                                                                                  project_name=metadata['project_name'],
#                                                                                                                  files=json.dumps(metadata['files']),
#                                                                                                                  last_updated=metadata['last_updated']).execute()
#         print('updated')
#     return True


def update_project_mongo(mongo_db, project_id, metadata, files_dict):
    project_data = mongo_db['project-data']
    files = mongo_db['files']
    # try:
    #     project_data.insert_one(metadata)
    # except pymongo.errors.DuplicateKeyError:
    if 'project_name' in metadata and metadata['project_name'] is not None:
        newname = { "$set": {"project_name": metadata['project_name'], "last_updated": metadata['last_updated']} }
        project_data.update_one({"_id": project_id}, newname)
    if 'user_list' in metadata and metadata['user_list'] is not None:
        newuser = {"$push": {"user_list": metadata['user_list']}}
        project_data.update_one({"_id": project_id}, newuser)
    if files_dict:
        files.insert_one(files_dict)
    updatequery = { "$set": {"last_updated": metadata['last_updated']}}
    project_data.update_one({"_id": project_id}, updatequery)



# def update_project_files(projects_table, project_id, metadata):
#     existing_info = projects_table.select().where(projects_table.columns.project_id == project_id).execute().fetchone()
#     if existing_info[3] is not None:
#         metadata['files'] = [metadata['files'], existing_info[3]]
#     update_statement = projects_table.update().where(projects_table.columns.project_id == project_id).values(files=metadata['files'],
#                                                                                                              last_updated=metadata['last_updated']).execute()
#     print('updated')
#     return True


# def get_projects(projects_table, email):
#     email = '{' + email + '}'
#     select_statement = sqlalchemy.select(projects_table).where(projects_table.columns.user_list.contains(email)).execute()
#     return select_statement.fetchall()


def get_projects_mongo(mongo_db, email):
    projects = mongo_db['project-data']
    res = projects.find({'user_list': email})
    project_list = []
    for project in res:
        project_list.append(project)
    print(project_list)
    return project_list


# def get_filename(projects_table, ipfs_hash):
#     select_statement = sqlalchemy.select(projects_table).where(projects_table.columns.ipfs_hash == ipfs_hash).execute()
#     res = select_statement.fetchone()
#     return res[3]


def get_filename_mongo(mongo_db, ipfs_hash):
    files = mongo_db['files']
    filename = files.find_one({"ipfs_hash": ipfs_hash}, {"filename": 1})
    print(filename['filename'])
    return filename['filename']


# def get_project_metadata(projects_table, project_id):
#     select_statement = sqlalchemy.select(projects_table).where(projects_table.columns.project_id == project_id).execute()
#     res = select_statement.fetchone()
#     return res


def get_project_metadata_mongo(mongo_db, project_id, active_only=True):
    project_data = mongo_db['project-data']
    files = mongo_db['files']
    metadata = project_data.find_one({"_id": project_id})
    query = {"project_id": project_id}
    if active_only:
        query.update({"active": True})
    file_data = files.find(query)
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
    project_data = mongo_db['project-data']
    project_id = files.find_one({"ipfs_hash": ipfs_hash}, {"project_id": 1, "filename": 1})
    files.update_one( {"ipfs_hash": ipfs_hash}, {"$set": {"active": False}})
    updatequery = {"$set": {"last_updated": datetime.datetime.utcnow().isoformat()}}
    project_data.update_one({"_id": project_id}, updatequery)
    return project_id['project_id'], project_id['filename']


def add_transaction_to_file(mongo_db, ipfs_hash, transaction_url):
    files = mongo_db['files']
    project_id = files.find_one({"ipfs_hash": ipfs_hash}, {"project_id": 1, "filename": 1})
    files.update_one({"ipfs_hash": ipfs_hash}, {"$set": {"transaction_url": transaction_url}})
    return project_id['project_id'], project_id['filename']


def remove_user(mongo_db, project_id, user):
    project_data = mongo_db['project-data']
    query = { "$pull": { "user_list": user}}
    project_data.update_one({"_id": project_id}, query)
    updatequery = {"$set": {"last_updated": datetime.datetime.utcnow().isoformat()}}
    project_data.update_one({"_id": project_id}, updatequery)


def init_project(mongo_db, user, transaction_url):
    project_data = mongo_db['project-data']
    # init_project_id = str(max(flow.getProjects()['collection']))
    timer = 0
    while timer < 10:
        time.sleep(3)
        init_project_id = str(ethereum.get_project_count() - 1)
        try:
            project_data.insert_one({"_id": init_project_id, "user_list": [user], "transaction_url": transaction_url,
                 "project_name": "Untitled Project"})
            return init_project_id
        except pymongo.errors.DuplicateKeyError:
            timer += 1
    return {"message": "New Project transaction timed out. Try increasing the gas limit."}



def add_license(mongo_db, license_id, transaction_url, num_prints, part_hash, licensed_by_email, licensed_to_email, licensed_by_address, licensed_to_address):
    license_data = mongo_db['license-data']
    license_data.insert_one({"_id": license_id, "transaction_url": transaction_url, "num_prints": num_prints,
                             "part_hash": part_hash, "licensed_by_email": licensed_by_email, "licensed_to_email": licensed_to_email,
                             "licensed_by_address": licensed_by_address, "licensed_to_address": licensed_to_address,
                             "prints": []})


def add_print(mongo_db, license_id, timestamp, operatorid, report_hash, transaction_url):
    license_data = mongo_db['license-data']

    newprint = {"$push": {"prints": {
        "timestamp": timestamp,
        "timestamp_str": datetime.datetime.now().isoformat(),
        "operator_id": operatorid,
        "report_hash": report_hash,
        "transaction_url": transaction_url
    }}}
    license_data.update_one({"_id": license_id}, newprint)



def get_licenses(mongo_db):
    license_data = mongo_db['license-data']
    license_list = []
    licenses = license_data.find()
    for license in licenses:
        license_list.append(license)
    return license_list


def get_print(mongo_db, license_id, print_id):
    license_data = mongo_db['license-data']
    data = license_data.find_one({"_id": license_id})
    data['prints'] = data['prints'][print_id]
    return data


def add_build_data(mongodb, build_tree: dict, build_entries: list):
    build_trees_col = mongodb['build-trees']
    build_entries_col = mongodb['build-entries']
    build_trees_col.insert_one(build_tree)
    build_entries_col.insert_many(build_entries)


def get_build_trees(mongodb, projectid):
    build_trees = mongodb['build-trees']
    tree_list = []
    trees = build_trees.find({"project_id": projectid}, {"_id": 1})
    for tree in trees:
        tree_list.append(tree)
    return tree_list


def get_tree_by_uid(mongodb, uid):
    build_trees = mongodb['build-trees']
    tree = build_trees.find_one({"UID": uid})
    return tree


def get_build_entries(mongodb, query: dict = None, output: dict = None):
    build_entries = mongodb['build-entries']
    entry_list = []
    entries = build_entries.find(query, output)
    for entry in entries:
        entry_list.append(entry)
    return entry_list


def update_entry_files(mongodb, uid, file_metadata):
    build_entries = mongodb['build-entries']
    query = {"UID": uid}
    newvalues = {"$push": {"files": file_metadata}}
    build_entries.update_one(query, newvalues)


def update_tree_files(mongodb, uid, file_metadata):
    build_tree = mongodb['build-trees']
    res = build_tree.find_one({"Part.UID": uid}, {"Part": 1})
    if res:
        for i in range(len(res['Part'])):
            if res['Part'][i]['UID'] == uid:
                idx = i
            else:
                continue
        set_value = "Part." + str(idx) + ".files"
        res = build_tree.update_one({"Part.UID": uid}, {"$push": {set_value: file_metadata}})
    else:
        res = build_tree.find_one({"UID": uid}, {"Part": 1})
        if res:
            res = build_tree.update_one({"UID": uid}, {"$push": {"files": file_metadata}})


def update_entry_output(mongodb, uid, output_type, output_value):
    build_entries = mongodb['build-entries']
    query = {"UID": uid}
    newvalues = {"$set": {output_type: output_value}}
    build_entries.update_one(query, newvalues)


def update_tree_output(mongodb, uid, output_type, output_value):
    build_tree = mongodb['build-trees']
    res = build_tree.find_one({"Part.UID": uid}, {"Part": 1})
    if res:
        for i in range(len(res['Part'])):
            if res['Part'][i]['UID'] == uid:
                idx = i
            else:
                continue
        set_value = "Part." + str(idx) + "." + output_type
        res = build_tree.update_one({"Part.UID": uid}, {"$set": {set_value: output_value}})
    else:
        res = build_tree.find_one({"UID": uid}, {"Part": 1})
        if res:
            res = build_tree.update_one({"UID": uid}, {"$set": {output_type: output_value}})