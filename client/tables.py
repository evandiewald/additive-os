from sqlalchemy import Table, Column, String, MetaData, create_engine, Integer, JSON
from sqlalchemy.dialects.postgresql import ARRAY


def users_table(db):
    table = Table('users', MetaData(db),
                        Column('username', String, primary_key=True, nullable=False),
                        Column('pwhash', String, nullable=False),
                        Column('name', String, nullable=False))
    return table


def projects_table(db):
    table = Table('projects', MetaData(db),
                  Column('project_id', Integer, primary_key=True, nullable=False),
                  Column('project_name', String, nullable=True),
                  Column('user_list', String, nullable=True),
                  Column('files', String, nullable=True),
                  Column('last_updated', String, nullable=True))
    return table