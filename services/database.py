import os
import mysql.connector
from mysql.connector import pooling

_pool_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'database': os.getenv('DB_NAME', 'matheuspersonal'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'pool_name': os.getenv('DB_POOL_NAME', 'mypool'),
    'pool_size': int(os.getenv('DB_POOL_SIZE', 2)),
    'pool_reset_session': True,
    'connection_timeout': 30,
}

connection_pool = pooling.MySQLConnectionPool(**_pool_config)

def get_db():
    conn = connection_pool.get_connection()
    try:
        conn.ping(reconnect=False)
    except mysql.connector.errors.OperationalError:
        conn.close()
        conn = connection_pool.get_connection()
    return conn
