import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from app.config import db_config

# Connect to default database (usually 'postgres') to create our database
try:
    conn = psycopg2.connect(
        host=db_config.host,
        port=db_config.port,
        user=db_config.username,
        password=db_config.password,
        database='postgres'  # connect to default database
    )
except psycopg2.OperationalError as e:
    # If we can't connect to 'postgres', try to connect to the default maintenance database
    conn = psycopg2.connect(
        host=db_config.host,
        port=db_config.port,
        user=db_config.username,
        password=db_config.password
    )
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cursor = conn.cursor()

# Check if database exists
cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (db_config.database,))
exists = cursor.fetchone()
if not exists:
    cursor.execute(f'CREATE DATABASE "{db_config.database}"')
    print(f"Database '{db_config.database}' created.")
else:
    print(f"Database '{db_config.database}' already exists.")

cursor.close()
conn.close()