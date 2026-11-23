
import requests
import xml.etree.ElementTree as ET

def fetch_rss_news():
    try:
        url = "https://cointelegraph.com/rss"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        print(f"Fetching RSS: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            items = root.findall('.//item')
            print(f"Found {len(items)} items")
            
            news_list = []
            for item in items[:5]:
                title = item.find('title').text
                link = item.find('link').text
                print(f"- {title}")
                news_list.append({'title': title, 'url': link})
            return news_list
        else:
            print(f"Error: {response.status_code}")
            return []
    except Exception as e:
        print(f"RSS Error: {e}")
        return []

fetch_rss_news()
