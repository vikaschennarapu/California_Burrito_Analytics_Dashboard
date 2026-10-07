import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

ssl_ca = os.getenv("DB_SSL_CA")
args = {"ssl": {"ca": ssl_ca}} if ssl_ca else {}
engine = create_engine(os.environ["DATABASE_URL"], connect_args=args, pool_pre_ping=True)

print("Reading CSV...")
df = pd.read_csv("data/orders.csv.gz", parse_dates=["Order_Datetime"])
df.columns = [c.lower() for c in df.columns]
df = df.rename(columns={"billno": "bill_no", "group": "item_group"})

assert df.isna().sum().sum() == 0, "missing values found"
assert (df.quantity > 0).all(), "bad quantity found"

df["revenue"] = df.price * df.quantity
df["order_date"] = df.order_datetime.dt.date
df["order_month"] = df.order_datetime.dt.strftime("%Y-%m")
df["order_hour"] = df.order_datetime.dt.hour

print("Creating table...")
with engine.begin() as conn:
    conn.execute(text("DROP TABLE IF EXISTS line_items"))
    conn.execute(text(open("etl/schema.sql", encoding="utf-8").read()))

print("Loading rows (a few minutes)...")
df.to_sql("line_items", engine, if_exists="append", index=False,
          chunksize=2000, method="multi")

with engine.connect() as conn:
    row = conn.execute(text(
        "SELECT COUNT(*), COUNT(DISTINCT bill_no), SUM(revenue), SUM(quantity) FROM line_items"
    )).one()
print("Result:", tuple(row))
print("Expected: (300000, 110478, 69480952, 434448)")