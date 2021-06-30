import pymongo
import config
import json
import database
import networkx as nx
import matplotlib.pyplot as plt
from pyvis.network import Network

# MongoDB
mongo_client = pymongo.MongoClient(config.MONGO_CONNECTION_STRING)
mongo_db = mongo_client.amblockchain

def visualize_tree(mongodb, project_id, tree_idx):
    trees = database.get_build_trees(mongo_db, project_id)

    uid = trees[tree_idx]

    tree = database.get_tree_by_uid(mongodb, uid['_id'])

    net = Network(width="100%", height="75%")

    i = 1
    net.add_node(i, label=tree['UID'])
    i += 1
    for key in tree.keys():
        if key == 'UID':
            continue
        else:
            if type(tree[key]) is list:
                net.add_node(i, label=key, color='#ffb500')
                net.add_edge(1, i)
                parent_id = i
                i += 1
                for child in tree[key]:
                    net.add_node(i, label=child['UID'], color='#eb0a77')
                    net.add_edge(parent_id, i)
                    child_id = i
                    i += 1
                    for subkey in child.keys():
                        if type(child[subkey]) is list:
                            pass
                        else:
                            net.add_node(i, label=subkey, title=str(child[subkey]), color='#00a999')
                            net.add_edge(child_id, i)
                            i += 1
            else:
                net.add_node(i, label=key, title=str(tree[key]), color='#00c585')
                net.add_edge(1, i)
                i += 1
    # net.show_buttons()
    net.set_options("""
    var options = {
      "nodes": {
        "physics": false
      },
      "edges": {
        "color": {
          "inherit": true
        },
        "physics": false,
        "smooth": false
      },
      "layout": {
        "hierarchical": {
          "enabled": true
        }
      },
      "interaction": {
        "hover": true,
        "multiselect": true,
        "navigationButtons": true
      },
      "physics": {
        "enabled": false,
        "hierarchicalRepulsion": {
          "centralGravity": 0
        },
        "minVelocity": 0.75,
        "solver": "hierarchicalRepulsion"
      }
    }""")


    net.save_graph('templates/graph.html')