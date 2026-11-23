
import requests
import xml.etree.ElementTree as ET

FEEDS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://decrypt.co/feed",
    "https://beincrypto.com/feed/"
]

def test_feeds():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for url in FEEDS:
        print(f"\nTesting: {url}")
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                print("✅ Success")
                # Try simple parsing
                try:
                    root = ET.fromstring(response.content)
                    items = root.findall('.//item')
                    print(f"   Found {len(items)} items")
                    if items:
                        print(f"   Sample: {items[0].find('title').text}")
                except Exception as parse_err:
                    print(f"⚠️ Parse Error: {parse_err}")
            else:
                print(f"❌ Failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Error: {e}")

test_feeds()
