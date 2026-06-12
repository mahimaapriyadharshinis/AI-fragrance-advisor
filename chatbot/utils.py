import os
import ast
import pandas as pd
import requests
from pymongo import MongoClient
from django.conf import settings

# 1. Initialize MongoDB Client Connection
import certifi

def get_mongo_db():
    # Force use of tlsCAFile using certifi bundle to fix newer OpenSSL 3 handshake issues with Atlas replica sets
    client = MongoClient(
        settings.MONGO_URI,
        tls=True,
        tlsCAFile=certifi.where(),
        retryWrites=False
    )
    return client[settings.MONGO_DB_NAME]

# 2. CSV Data Handler Script
def import_csv_to_mongodb():
    db = get_mongo_db()
    collection = db["fragrances"]
    
    # Locate the CSV file inside our folder tree
    csv_path = os.path.join(settings.BASE_DIR, 'data', 'fragrances.csv')
    
    if not os.path.exists(csv_path):
        return {"status": "error", "message": f"CSV file not found at {csv_path}"}
        
    df = pd.read_csv(csv_path)
    
    # Drop existing elements to prevent row duplication on multiple runs
    collection.delete_many({})
    
    records = []
    for _, row in df.iterrows():
        # Handle string lists securely safely converting "['a', 'b']" -> ['a', 'b']
        try:
            accords = ast.literal_eval(row['Main Accords']) if isinstance(row['Main Accords'], str) else []
        except (ValueError, SyntaxError):
            accords = []
            
        try:
            perfumers = ast.literal_eval(row['Perfumers']) if isinstance(row['Perfumers'], str) else []
        except (ValueError, SyntaxError):
            perfumers = []

        record = {
            "name": str(row['Name']),
            "gender": str(row['Gender']).strip().lower(),
            "rating_value": float(row['Rating Value']) if not pd.isna(row['Rating Value']) else 0.0,
            "rating_count": int(str(row['Rating Count']).replace(',', '')) if not pd.isna(row['Rating Count']) else 0,
            "main_accords": [accord.strip().lower() for accord in accords],
            "perfumers": perfumers,
            "description": str(row['Description'])
        }
        records.append(record)
        
    if records:
        collection.insert_many(records)
        return {"status": "success", "count": len(records)}
    return {"status": "error", "message": "No valid rows extracted"}

# 3. Core Sarvam AI Integration Layer
def call_sarvam_ai(messages_list):
    """
    Handles request pipelines to the Sarvam Chat Completion endpoint
    """
    url = "https://api.sarvam.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "API-Subscription-Key": settings.SARVAM_API_KEY
    }
    
    payload = {
        "model": "sarvam-30b",
        "messages": messages_list,
        "temperature": 0.4 # Balanced temperature for persuasive and luxurious recommendations
    }
    
    try:
        # Increased timeout to 45s to handle slower external network connections or complex generations
        response = requests.post(url, json=payload, headers=headers, timeout=45)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"Error from Sarvam API: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Connection Failed: {str(e)}"