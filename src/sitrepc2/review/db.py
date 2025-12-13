import sqlite3
from sitrepc2.config.paths import get_lss_db_path

def connect():
    return sqlite3.connect(get_lss_db_path())
