import os
import glob
import json
import yaml
from pathlib import Path
from pymongo import MongoClient

# Load secrets and MongoDB config directly
yaml_path = Path(__file__).parent / "newspapers_scrap" / "config" / "secrets.yaml"
with open(yaml_path, 'r') as f:
    secrets = yaml.safe_load(f)

mongo_conf = secrets.get("mongodb", {})

# MongoDB connection
client = MongoClient(mongo_conf.get("uri"))
db = client[mongo_conf.get("database", "press_processed")]
collection = db[mongo_conf.get("collection", "articles")]

# Directory with processed articles
data_dir = Path(__file__).parent / "data" / "processed"

# Find all JSON files in processed directory
json_files = glob.glob(str(data_dir / "*.json"))

inserted = 0
for file_path in json_files:
    with open(file_path, 'r', encoding='utf-8') as f:
        article = json.load(f)
        # Insert into MongoDB (upsert by 'id' if needed)
        collection.update_one({'id': article['id']}, {'$set': article}, upsert=True)
        inserted += 1

print(f"Inserted or updated {inserted} articles into MongoDB collection '{mongo_conf.get('collection', 'articles')}' in database '{mongo_conf.get('database', 'press_processed')}'.")
