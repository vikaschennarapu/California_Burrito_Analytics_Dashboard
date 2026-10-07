import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
args = {"ssl": {"ca": os.environ["DB_SSL_CA"]}}
engine = create_engine(os.environ["DATABASE_URL"], connect_args=args)
with engine.connect() as conn:
    print("Connected. MySQL version:", conn.execute(text("SELECT VERSION()")).scalar())