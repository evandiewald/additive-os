import requests
import json
import config

FLOW_API_URL = config.FLOW_API_URL


def getProjects():
    r = requests.get(FLOW_API_URL + '/projects/collection/0x4263f3e1effb2e48')
    return r.json()


def getMetadata(projectId: str):
    r = requests.get(FLOW_API_URL + '/projects/' + str(projectId))
    return r.json()


def newProject():
    r = requests.post(FLOW_API_URL + '/projects/new')
    return r.json()


def updateProject(projectId: str, metadata):
    metadata_str = json.dumps(metadata)
    data = {"newMetadata": metadata}
    r = requests.post(FLOW_API_URL + '/projects/update/' + str(projectId), data=data)
    print(r.url)
    # return r.json()