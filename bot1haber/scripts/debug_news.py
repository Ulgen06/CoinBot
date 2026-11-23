
import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from env_loader import load_env
load_env()

import requests
import json
import hashlib

CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY", "")
MACRO_KEYWORDS = ["cpi", "fomc", "rate hike", "inflation", "powell", "gdp", "non-farm", "unemployment", "fed"]

def get_ai_sentiment(text):
    # Dummy sentiment for debugging
    return "neutral", "⚖️ Nötr", 0

def calculate_impact_score(votes, sentiment_score, source, is_macro):
    """Haberin önem derecesini (0-10) hesaplar."""
    score = 0
    
    # Vote etkisi
    if votes > 20: score += 4
    elif votes > 10: score += 3
    elif votes > 5: score += 2
    
    # Kaynak Güvenilirliği
    trusted = ['binance', 'coinbase', 'cointelegraph', 'bloomberg', 'reuters', 'sec.gov']
    if any(t in source.lower() for t in trusted):
        score += 2
        
    # Sentiment Şiddeti (Mutlak değer)
    score += abs(sentiment_score) * 3
    
    # Macro Faktörü
    if is_macro:
        score += 3
        
    return min(round(score, 1), 10)

def fetch_cryptopanic_ultimate():
    try:
        url = "https://cryptopanic.com/api/v1/posts/"
        params = {
            "auth_token": CRYPTOPANIC_API_KEY,
            "filter": "hot",
            "public": "true",
            "kind": "news"
        }
        print(f"Requesting: {url} with filter=hot")
        response = requests.get(url, params=params, timeout=10)
        results = []
        
        if response.status_code == 200:
            results = response.json().get('results', [])
            print(f"Hot results count: {len(results)}")
        else:
            print(f"Error: {response.status_code} - {response.text}")
        
        # Eğer hot haber yoksa normal haberleri getir
        if not results:
            print("No hot results, trying filter=all")
            params['filter'] = 'all' 
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                results = response.json().get('results', [])
                print(f"All results count: {len(results)}")
            else:
                print(f"Error: {response.status_code} - {response.text}")
                
        return results
    except Exception as e:
        print(f"❌ CryptoPanic Hatası: {e}")
        return []

print("Fetching news...")
news = fetch_cryptopanic_ultimate()
print("-" * 30)

for item in news:
    title = item.get('title', '')
    source = item.get('domain', 'Unknown')
    votes = item.get('votes', {}).get('positive', 0)
    
    sentiment, sent_label, sent_score = get_ai_sentiment(title)
    is_macro = any(kw in title.lower() for kw in MACRO_KEYWORDS)
    impact_score = calculate_impact_score(votes, sent_score, source, is_macro)
    
    print(f"Title: {title}")
    print(f"Source: {source} | Votes: {votes} | Macro: {is_macro}")
    print(f"Score: {impact_score}")
    if impact_score < 4 and not is_macro:
        print("❌ FILTERED OUT")
    else:
        print("✅ PASSED")
    print("-" * 30)
