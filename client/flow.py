import requests
import json
import config

FLOW_API_URL = config.FLOW_API_URL


def getProjects():
    r = requests.get(FLOW_API_URL + '/projects/collection/0x5cc83cb6d766bf4a')
    return r.json()


def getMetadata(projectId: str):
    r = requests.get(FLOW_API_URL + '/projects/' + str(projectId))
    # try:
    response = r.json()
    response = json.loads(response['collection'])
    response = response.replace('\'', '"')[1:-1].replace('}, {', '}}, {{').split('}, {')
    blockchain_data = []
    for block in response:
        blockchain_data.append(json.loads(block))
    response = blockchain_data
    # except:
    #     response = {}
    return response


def newProject():
    r = requests.post(FLOW_API_URL + '/projects/new')
    return True


def updateProject(projectId: str, metadata):
    metadata_str = json.dumps(metadata)
    data = {"newMetadata": metadata}
    r = requests.post(FLOW_API_URL + '/projects/update/' + str(projectId), data=data)
    print(r.url)
    # return r.json()