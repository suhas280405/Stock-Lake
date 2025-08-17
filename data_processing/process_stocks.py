# EquiLake/data_processing/process_stocks.py

import os
import json
import pandas as pd
from datetime import datetime
import boto3
import logging
import io
from dotenv import load_dotenv
import streamlit as st



# === Load environment variables or secrets ===
if "S3_BUCKET" in st.secrets:
    S3_BUCKET = st.secrets["S3_BUCKET"]
    AWS_REGION = st.secrets["AWS_REGION"]
else:
    load_dotenv()
    S3_BUCKET = os.getenv("S3_BUCKET")
    AWS_REGION = os.getenv("AWS_REGION")

# === Config ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
TODAY = datetime.today().strftime("%Y-%m-%d")
STOCK_SYMBOLS = ["AAPL", "TSLA", "GOOGL", "AMZN", "MSFT"]



# === Utilities ===
def download_json_from_s3(key):
    try:
        s3 = boto3.client("s3", region_name=AWS_REGION)
        response = s3.get_object(Bucket=S3_BUCKET, Key=key)
        return json.loads(response["Body"].read().decode("utf-8"))
    except Exception as e:
        logging.error(f"❌ Failed to download {key} from S3: {e}")
        return {}

def process_stocks():
    for symbol in STOCK_SYMBOLS:
        logging.info(f"📊 Processing stock data for {symbol}...")
        raw_key = f"raw/stocks/{symbol}_{TODAY}.json"
        data = download_json_from_s3(raw_key)

        if not data:
            logging.warning(f"⚠ No data found for {symbol}")
            continue

        # Handle API errors
        if "Note" in data:
            logging.warning(f"⚠ API limit reached for {symbol}: {data['Note']}")
            continue
        if "Error Message" in data:
            logging.warning(f"⚠ API error for {symbol}: {data['Error Message']}")
            continue

        time_series = data.get("Time Series (Daily)", {})
        if not time_series:
            logging.warning(f"⚠ Missing 'Time Series (Daily)' for {symbol}")
            continue

        try:
            df = pd.DataFrame.from_dict(time_series, orient="index").reset_index()
            df.columns = ["date", "open", "high", "low", "close", "volume"]
            df = df.astype({
                "open": "float",
                "high": "float",
                "low": "float",
                "close": "float",
                "volume": "int64"
            })
            df["date"] = pd.to_datetime(df["date"])
            df["symbol"] = symbol
            df = df[["date", "symbol", "open", "high", "low", "close", "volume"]]

            upload_df_to_s3(df, symbol)

        except Exception as e:
            logging.error(f"❌ Failed to process {symbol}: {e}")

def upload_df_to_s3(df, symbol):
    s3 = boto3.client("s3", region_name=AWS_REGION)
    try:
        key = f"processed/stocks/{symbol}_{TODAY}.parquet"
        buffer = io.BytesIO()
        df.to_parquet(buffer, index=False)
        buffer.seek(0)
        s3.upload_fileobj(buffer, S3_BUCKET, key)
        logging.info(f"✅ Uploaded to s3://{S3_BUCKET}/{key}")
    except Exception as e:
        logging.error(f"❌ Upload failed for {symbol}: {e}")

# === Main ===


# === Entry Point ===
if __name__ == "__main__":
    process_stocks()
