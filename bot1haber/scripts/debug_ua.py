
import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from env_loader import load_env
load_env()

import requests
import json

CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY", "")

def fetch_cryptopanic_ultimate():
    try:
        url = "https://cryptopanic.com/api/v1/posts/"
        params = {
            "auth_token": CRYPTOPANIC_API_KEY,
            "public": "true"
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        print(f"Requesting: {url} (Basic params)")
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text[:500]}") # Print first 500 chars

    except Exception as e:
        print(f"❌ Hatası: {e}")

fetch_cryptopanic_ultimate()
