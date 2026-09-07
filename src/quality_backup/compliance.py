import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

def get_engine():
    database_url=os.getenv("MEYAAR_DATABASE_URL")
    if not database_url:
        raise RuntimeError("MEYAAR_DATABASE_URL is not configured.")
    return create_engine(database_url,pool_pre_ping=True)