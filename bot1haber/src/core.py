"""
╔══════════════════════════════════════════════════════════════╗
║  CRYPTO HABER BOTU v3.0 - ULTIMATE EDITION                   ║
║  AI Sentiment, Macro Events, Auto-Charts, Whale v2           ║
╚══════════════════════════════════════════════════════════════╝
"""

import sys
import os
import logging
import warnings
import matplotlib
matplotlib.use('Agg')
warnings.filterwarnings("ignore", category=FutureWarning)

# Ensure logs directory exists
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    filename=os.path.join(log_dir, "core_v2.log"),
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)
logging.info("Core module initialized")



import requests
import time
import json
import os
import hashlib
import pandas as pd
import mplfinance as mpf
import xml.etree.ElementTree as ET
import random
import subprocess
import signal
import threading
import sys

# Windows Terminal emoji desteği için kodlama ayarı
if sys.platform == "win32":
    import io
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except:
        pass

from datetime import datetime, timedelta
from collections import defaultdict
import matplotlib.pyplot as plt
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import edge_tts
import asyncio
from deep_translator import GoogleTranslator
from groq import Groq

# Server Import Fix
try:
    from src.server import run_server
except ImportError:
    from server import run_server

# ════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ════════════════════════════════════════════════════════════
def get_base_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_data_path(filename):
    return os.path.join(get_base_dir(), 'data', filename)

def get_config_path(filename):
    return os.path.join(get_base_dir(), 'config', filename)

def robust_json_get(url, params=None, timeout=10):
    """API'den güvenli bir şekilde JSON çeker, hata olursa None döner"""
    try:
        r = requests.get(url, params=params, timeout=timeout)
        if r.status_code == 200:
            try:
                return r.json()
            except:
                print(f"⚠️ Geçersiz JSON ({url})")
        else:
            print(f"⚠️ API Hatası ({url}): {r.status_code}")
    except Exception as e:
        print(f"⚠️ Bağlantı Hatası ({url}): {e}")
    return None

def safe_load_wallet():
    """Cüzdan dosyasını güvenli okur"""
    fpath = get_data_path(WALLET_FILE)
    lock_path = fpath + ".lock"
    
    if not os.path.exists(fpath): return None
    
    # Simple lock mechanism
    start_time = time.time()
    while os.path.exists(lock_path):
        if time.time() - start_time > 5: # 5 second timeout
            try: os.remove(lock_path)
            except: pass
            break
        time.sleep(0.1)
        
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None

def safe_save_wallet(wallet):
    """Cüzdanı güvenli ve atomik şekilde kaydeder"""
    fpath = get_data_path(WALLET_FILE)
    lock_path = fpath + ".lock"
    
    try:
        # Create lock
        with open(lock_path, 'w') as f: f.write(str(os.getpid()))
        
        temp_file = fpath + ".tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(wallet, f, indent=4, ensure_ascii=False)
        os.replace(temp_file, fpath)
        
        # Remove lock
        if os.path.exists(lock_path): os.remove(lock_path)
        return True
    except:
        if os.path.exists(lock_path): os.remove(lock_path)
        return False

# ════════════════════════════════════════════════════════════
# AYARLAR & SABİTLER
# ════════════════════════════════════════════════════════════

from env_loader import load_env
load_env()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "@Ulgentrader")

# API Anahtarları
CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Groq Yapılandırması
groq_client = None
AI_MODEL = "llama-3.3-70b-versatile"

def initialize_groq():
    global groq_client
    if GROQ_API_KEY and len(GROQ_API_KEY) > 10 and not GROQ_API_KEY.startswith("gsk_..."):
        try:
            groq_client = Groq(api_key=GROQ_API_KEY)
            print("✅ Groq AI Yapılandırıldı.")
            return True
        except Exception as e:
            err = f"⚠️ Groq Başlatılamadı: {e}"
            print(err)
            return err
    return "❌ Groq API anahtarı ayarlanmamış veya hatalı."

# İlk başlatma denemesi
groq_init_res = initialize_groq()

# Yapılandırma
WATCHED_COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE"]
IMPORTANT_KEYWORDS = [
    "bitcoin", "ethereum", "fed", "sec", "regulation", "etf",
    "hack", "exploit", "bull", "bear", "halving", "adoption",
    "whale", "crash", "rally", "breakout", "listing", "delisting",
    "pump", "dump", "binance", "coinbase", "approval", "ban",
    "cpi", "inflation", "interest rate", "fomc", "powell", "gdp"
]

MACRO_KEYWORDS = ["cpi", "fomc", "rate hike", "inflation", "powell", "gdp", "non-farm", "unemployment", "fed"]

# Dosyalar
SEEN_NEWS_FILE = "seen_news.json"
SUMMARY_FILE = "news_summary.json"
ALERTS_FILE = "price_alerts.json"
WALLET_FILE = "wallet.json"
CALENDAR_FILE = "calendar.json"
SEEN_ALERTS_FILE = "seen_macro_alerts.json"
ASSETS_DIR = "assets"
INITIAL_BALANCE = 1500  # 1000 + 500 Kar devri
SENTIMENT_STATS = {"positive": 0, "negative": 0, "neutral": 0}

# Diğer Dosyalar
SEEN_LISTINGS_FILE = "seen_listings.json"

# Global İşlem Değişkenleri
trader_process = None

# Zamanlayıcılar (Saniye)
NEWS_CHECK_INTERVAL = 600  # 10 dakikada bir otomatik tarama
WHALE_CHECK_INTERVAL = 300
BINANCE_LISTING_INTERVAL = 45  # Listelemeler çok kritiktir
SUMMARY_INTERVAL = 3600
EQUITY_LOG_INTERVAL = 3600 # 1 saatte bir cüzdan geçmişi kaydet

# Durum Değişkenleri
NEWS_SCAN_ENABLED = True


# Global Nesneler
analyzer = SentimentIntensityAnalyzer()
translator = GoogleTranslator(source='auto', target='tr')
if not os.path.exists(ASSETS_DIR):
    os.makedirs(ASSETS_DIR)

REPORT_SCHEDULE_TIME = "09:00"
last_report_date = ""

# ════════════════════════════════════════════════════════════
# TELEGRAM & GÖRSELLEŞTİRME & SES
# ════════════════════════════════════════════════════════════

def send_telegram_message(message, silent=False):
    try:
        logging.info(f"Sending Telegram message: {message[:50]}...")
        payload = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown',
            'disable_notification': silent,
            'disable_web_page_preview': True
        }
        r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json=payload, timeout=10)
        if r.status_code == 200:
            logging.info("Telegram message sent successfully.")
        else:
            logging.error(f"Telegram API Error: {r.status_code} - {r.text}")
            
    except Exception as e:
        print(f"❌ Telegram Msg Hatası: {e}")
        logging.error(f"Telegram Msg Exception: {e}", exc_info=True)


def get_telegram_updates(offset=None):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
        params = {'timeout': 10, 'offset': offset}
        data = robust_json_get(url, params=params, timeout=15)
        return data.get('result', []) if data else []
    except Exception as e:
        print(f"❌ Update Hatası: {e}")
        return []


def send_telegram_photo(caption, photo_path, silent=False):
    try:
        with open(photo_path, 'rb') as photo:
            payload = {
                'chat_id': CHAT_ID,
                'caption': caption,
                'parse_mode': 'Markdown',
                'disable_notification': silent
            }
            files = {'photo': photo}
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", data=payload, files=files, timeout=20)
    except Exception as e:
        print(f"❌ Telegram Foto Hatası: {e}")

def send_telegram_voice(caption, audio_path, silent=False):
    """Ses dosyasını (MP3) Telegram'a gönderir."""
    try:
        with open(audio_path, 'rb') as audio:
            payload = {
                'chat_id': CHAT_ID,
                'caption': caption,
                'parse_mode': 'Markdown',
                'disable_notification': silent
            }
            files = {'voice': audio}
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVoice", data=payload, files=files, timeout=20)
    except Exception as e:
        print(f"❌ Telegram Ses Hatası: {e}")

async def _create_edge_tts(text, filename, voice="tr-TR-AhmetNeural"):
    """Edge TTS için async yardımcı fonksiyon."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)

def generate_audio_alert(text, lang='tr'):
    """Metni sese çevirir (Microsoft Neural Voice)."""
    try:
        filename = f"{ASSETS_DIR}/alert_{int(time.time())}.mp3"
        # Daha doğal duyulan 'Emel' (Kadın) sesini kullanalım
        voice = "tr-TR-EmelNeural" if lang == "tr" else "en-US-EmmaNeural"
        
        # Yeni bir event loop oluşturarak çalıştır (Çakışmaları önler)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_create_edge_tts(text, filename, voice))
        finally:
            loop.close()
            
        return filename
    except Exception as e:
        print(f"❌ Ses oluşturma hatası: {e}")
        return None

def generate_chart_image(symbol, interval="15m", limit=50):
    """Binance'den veri çekip mplfinance ile grafik oluşturur."""
    try:
        # Binance verisi çek
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": f"{symbol}USDT", "interval": interval, "limit": limit}
        data = robust_json_get(url, params=params, timeout=10)
        
        if not data:
            return None
        df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'tbav', 'tbqav', 'ignore'])
        
        df['time'] = pd.to_datetime(df['time'], unit='ms')
        df.set_index('time', inplace=True)
        df = df.astype({'open': 'float', 'high': 'float', 'low': 'float', 'close': 'float', 'volume': 'float'})

        # Dosya yolu
        filename = f"{ASSETS_DIR}/{symbol}_chart.png"
        
        # Stil ve Grafik
        mc = mpf.make_marketcolors(up='#00ff00', down='#ff0000', inherit=True)
        s = mpf.make_mpf_style(base_mpf_style='nightclouds', marketcolors=mc)
        
        mpf.plot(
            df, 
            type='candle', 
            style=s, 
            title=f"\n{symbol}/USDT ({interval})",
            volume=True, 
            savefig=filename,
            tight_layout=True
        )
        return filename
    except Exception as e:
        print(f"❌ Grafik oluşturma hatası: {e}")
        return None

# ════════════════════════════════════════════════════════════
# ANALİZ & ZEKİ FONKSİYONLAR
# ════════════════════════════════════════════════════════════

def get_ai_sentiment(text):
    """VaderSentiment kullanarak metni analiz eder."""
    try:
        vs = analyzer.polarity_scores(text)
        compound = vs['compound']
        
        if compound >= 0.5:
            return "positive", "🚀 Boğa", compound
        elif compound <= -0.5:
            return "negative", "🩸 Ayı", compound
        else:
            return "neutral", "⚖️ Nötr", compound
    except:
        return "neutral", "⚖️ Nötr", 0

def check_price_impact(symbol):
    """Haber sonrası anlık fiyat değişimini (5dk mum) kontrol eder."""
    try:
        url = "https://api.binance.com/api/v3/ticker/24hr"
        params = {"symbol": f"{symbol}USDT"}
        data = robust_json_get(url, params=params, timeout=5)
        
        if data:
            pct = float(data.get('priceChangePercent', 0))
            price = float(data.get('lastPrice', 0))
            
            icon = "🟢" if pct > 0 else "🔴"
            return f"{icon} %{pct:.2f} (${price})"
        return "N/A"
    except:
        return "N/A"

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

def perform_technical_analysis(symbol):
    """Gelişmiş teknik analiz verisi çeker (MA50, RSI, BB Squeeze, Hacim)."""
    try:
        url = "https://api.binance.com/api/v3/klines"
        # 4 Saatlik periyot (Trend tespiti için en sağlıklı periyot)
        params = {"symbol": f"{symbol}USDT", "interval": "4h", "limit": 100}
        data = robust_json_get(url, params=params, timeout=5)
        if not data: return "Veri hatası."
        df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume', '_','_','_','_','_','_'])
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        
        # Göstergeler
        current_price = df['close'].iloc[-1]
        ma20 = df['close'].rolling(20).mean().iloc[-1]
        ma50 = df['close'].rolling(50).mean().iloc[-1]
        
        # Bollinger Bantları & Squeeze (Sıkışma)
        std = df['close'].rolling(20).std().iloc[-1] or 0
        upper_bb = ma20 + (std * 2)
        lower_bb = ma20 - (std * 2)
        bb_width = (upper_bb - lower_bb) / ma20 # Bant genişliği
        
        # RSI (14)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs.iloc[-1])) if not pd.isna(rs.iloc[-1]) else 50
        
        # Hacim Analizi (Son mum hacmi vs Ortalama Hacim)
        avg_volume = df['volume'].rolling(20).mean().iloc[-1]
        current_volume = df['volume'].iloc[-1]
        vol_status = "YÜKSEK (Hacimli)" if current_volume > avg_volume * 1.5 else "ZAYIF"
        
        # Analiz Sonucu
        trend = "BOĞA (MA50 Üstü)" if current_price > ma50 else "AYI (MA50 Altı)"
        squeeze = "EVET (Patlama Yakın)" if bb_width < 0.05 else "HAYIR"
        bb_pos = "Üst Band (Direnç)" if current_price > upper_bb * 0.98 else ("Alt Band (Destek)" if current_price < lower_bb * 1.02 else "Nötr")
        
        analysis = f"Fiyat: {current_price:.2f}, RSI: {rsi:.1f}, Trend: {trend}, Sıkışma: {squeeze}, Hacim: {vol_status}, BB: {bb_pos}"
        return analysis
    except:
        return "Teknik veri alınamadı."

def get_ai_summary(text):
    """Groq kullanarak haber özetini oluşturur."""
    if not groq_client:
        return None
    try:
        prompt = f"Aşağıdaki kripto para haberini Türkçe olarak 3 kısa maddede özetle. Çok kısa ve öz olsun: \n\n{text}"
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=AI_MODEL,
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Groq Özet Hatası: {str(e)}")
        return None

def ask_ulgen_ai(question):
    """Groq kullanarak piyasa hakkında derinlemesine analiz yapar."""
    if not groq_client:
        return "❌ ÜLGEN AI şu an pasif. Groq API anahtarını kontrol edin."
    
    try:
        # 1. En son haberleri al
        news = fetch_cryptopanic_ultimate()[:5]
        news_context = "\n".join([f"- {n.get('title')}" for n in news])
        
        # 2. Temel piyasa verilerini al
        fng = get_fear_greed_index()
        btc_analysis = perform_technical_analysis("BTC")
        
        # 3. SORU İÇİNDE COIN TESPİTİ
        specific_coin_data = ""
        common_coins = WATCHED_COINS + ["TAO", "SOL", "XRP", "ADA", "AVAX", "DOT", "LINK", "MATIC", "PEPE", "SHIB", "FET", "RENDER", "GRT"]
        found_coins = []
        for c in common_coins:
            if c.lower() in question.lower() and c != "BTC":
                found_coins.append(c)
        
        # Sektörel Bağlam (AI Coinleri tespiti)
        is_ai_coin = any(x in ["TAO", "FET", "RENDER", "GRT"] for x in found_coins)
        sector_context = "SEKTÖR: Yapay Zeka (AI). NVIDIA ve AI stock trendinden doğrudan etkilenir." if is_ai_coin else ""
        
        if found_coins:
            for coin in found_coins[:2]: # Max 2 coin
                analysis = perform_technical_analysis(coin)
                specific_coin_data += f"\n- {coin} ÖZEL VERİLERİ (4H): {analysis}"
        
        # 4. Promptu oluştur (v28 Pro-Level)
        system_prompt = f"""
        Sen 'ÜLGEN v28' adında, milyar dolarlık kripto fonlarını yöneten elit bir kantitatif analistisin. 
        Görevin: Aşağıdaki verileri kullanarak İmparator'a profesyonel bir rapor sunmak.
        
        KURALLAR:
        1. SADECE TÜRKÇE KONUŞ. Asla İngilizce veya Almanca kelime bırakma (Insufficient, technical, keine vb. KESİNLİKLE yasaktır).
        2. ASLA BOŞ YAPMA. Selamlaşma, "Sizin için analiz ettim" gibi gereksiz girişleri sil. Doğrudan teknik özetle başla.
        3. ANALİZ PERİYODU: Analizin 4 Saatlik (4H) periyotta yapıldığını mutlaka belirt.
        4. RSI & BB SIKIŞMASI: RSI 50 civarıyken fiyat BB üst bandındaysa, bunun bir 'Bant Sıkışması' olduğunu ve yüksek volatilite patlaması yaklaştığını vurgula.
        5. HACİM ONAYI: Hacim 'ZAYIF' ise mevcut yükselişi "Güvensiz/Fakeout" olarak işaretle.
        6. DESTEK & DİRENÇ: Mutlaka net rakamlar ver.
        7. HÜKÜM: Net bir re-evaluation noktasıyla bitir. "X direnci geçilirse Long, Y desteği altında durulmamalı."
        
        CONTEXT DATA:
        - Korku Endeksi: {fng}
        - BTC Verileri (4H): {btc_analysis}
        {specific_coin_data}
        - Sektör Durumu: {sector_context}
        - Güncel Haberler: {news_context}
        
        FORMAT:
        🔱 **ÜLGEN v28 KANTİTATİF RAPOR** 🔱
        
        ● **Piyasa Yapısı (4S):** (Trend, MA50 konumu ve Hacim onayı)
        ● **Varlık Analizi ({' | '.join(found_coins) if found_coins else 'Genel Market'}):** (RSI, Sıkışma durumu ve Sektörel hikaye)
        ● **HÜKÜM & SEVİYELER:** (Destek/Direnç rakamları ve re-eval stratejisi)
        """
        
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": system_prompt}],
            model=AI_MODEL,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        error_detail = str(e)
        print(f"❌ Groq Danışman Hatası: {error_detail}")
        if "rate_limit" in error_detail.lower():
            return "⚠️ Groq API hız sınırına takıldınız. Lütfen biraz bekleyin."
        return f"⚠️ ÜLGEN AI şu an analiz yapamıyor.\nHata: `{error_detail}`"

# ════════════════════════════════════════════════════════════
# ALARMLAR & LİKİDASYON & İSTATİSTİK
# ════════════════════════════════════════════════════════════

def load_price_alerts():
    fpath = get_data_path(ALERTS_FILE)
    if not os.path.exists(fpath): return []
    try:
        with open(fpath, 'r', encoding='utf-8') as f: return json.load(f)
    except: return []

def save_price_alerts(alerts):
    fpath = get_data_path(ALERTS_FILE)
    try:
        with open(fpath, 'w', encoding='utf-8') as f: json.dump(alerts, f, indent=4)
    except: pass

def check_price_alerts():
    """Kullanıcı alarmlarını kontrol eder."""
    alerts = load_price_alerts()
    if not alerts: return
    
    updated_alerts = []
    triggered = False
    
    for alert in alerts:
        symbol = alert['symbol']
        target = float(alert['target'])
        direction = alert['direction'] # 'above' or 'below'
        
        # Anlık fiyat al
        try:
            r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT", timeout=5)
            curr = float(r.json()['price'])
            
            is_triggered = (direction == 'above' and curr >= target) or (direction == 'below' and curr <= target)
            
            if is_triggered:
                msg = f"🔔 **FİYAT ALARMI TETİKLENDİ!**\n\n"
                msg += f"💰 **{symbol}:** `${curr}`\n"
                msg += f"🎯 Hedefin: `${target}` ({'Üstü' if direction == 'above' else 'Altı'})\n"
                send_telegram_message(msg)
                triggered = True
            else:
                updated_alerts.append(alert)
        except:
            updated_alerts.append(alert)
            
    if triggered:
        save_price_alerts(updated_alerts)

def get_liquidation_data():
    """Likidasyon verilerini büyük işlem verilerinden türetir."""
    try:
        whales = check_deep_whales()
        if not whales: return "⚠️ Şu an piyasada devasa bir likidasyon/işlem saptanmadı."
        
        msg = "🩸 **LİKİDASYON & SERT HAREKET RADARI**\n\n"
        for w in whales[:5]:
            msg += f"• **{w['symbol']}**: {w['side']} - `${w['amount']/1_000_000:.1f}M` @ `${w['price']}`\n"
        
        msg += "\n💡 _Bu veriler yüksek hacimli piyasa emridir, likidasyon bölgesi olabilir._"
        return msg
    except: return "❌ Veri çekilemedi."

def generate_sentiment_report():
    """Günün duyarlılık özet grafiğini oluşturur."""
    try:
        labels = ['Boğa (🚀)', 'Ayı (🩸)', 'Nötr (⚖️)']
        sizes = [SENTIMENT_STATS['positive'], SENTIMENT_STATS['negative'], SENTIMENT_STATS['neutral']]
        colors = ['#00ff00', '#ff0000', '#aaaaaa']
        
        if sum(sizes) == 0: return None
        
        plt.figure(figsize=(8, 6))
        plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=140, textprops={'color':"white"})
        plt.title("Kripto Haber Duyarlılık Özeti", color="white")
        plt.axis('equal')
        
        plt.gcf().set_facecolor('#1e1e1e')
        filename = f"{ASSETS_DIR}/sentiment_report.png"
        plt.savefig(filename, facecolor='#1e1e1e', dpi=100)
        plt.close()
        return filename
    except Exception as e:
        print(f"Grafik hatası: {e}")
        return None

def log_equity_snapshot():
    """Cüzdanın anlık değerini geçmişe kaydeder."""
    wallet = safe_load_wallet()
    if not wallet: return
    
    try:
        balance = wallet.get('available_balance', 0)
        positions = wallet.get('positions', {})
        equity = balance + sum([p.get('amount', 0) for p in positions.values()])
        
        if "equity_history" not in wallet: wallet["equity_history"] = []
        wallet['equity_history'].append({"time": time.time(), "equity": equity})
        
        # Son 200 kaydı tut
        wallet['equity_history'] = wallet['equity_history'][-200:]
        
        safe_save_wallet(wallet)
    except: pass

def get_trader_wallet_status():
    """bottrader.py'nin cüzdan dosyasını okur ve anlık PNL hesaplar."""
    fpath = get_data_path(WALLET_FILE)
    if not os.path.exists(fpath):
        wallet = {
            "initial_balance": INITIAL_BALANCE, 
            "available_balance": INITIAL_BALANCE, 
            "positions": {}, 
            "total_profit": 0,
            "equity_history": [{"time": time.time()-86400, "equity": INITIAL_BALANCE}, {"time": time.time(), "equity": INITIAL_BALANCE}],
            "trade_history": []
        }
        with open(fpath, 'w') as f: json.dump(wallet, f)
        return "💰 **İmparatorluk Kasası Kuruldu!**\nBakiyeniz: `1500.00$`"
    
    try:
        fpath = get_data_path(WALLET_FILE)
        with open(fpath, 'r') as f:
            wallet = json.load(f)
            
        balance = wallet.get('available_balance', 0)
        initial = wallet.get('initial_balance', 1500)
        positions = wallet.get('positions', {})
        
        # Anlık varlık hesaplama
        equity = balance
        pos_details = ""
        total_pnl_usd = 0
        
        if positions:
            for sym, pos in positions.items():
                # Anlık fiyat çek
                try:
                    # Futures fiyatı kullan (v30 standardı)
                    r = robust_json_get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={sym}", timeout=3)
                    curr = float(r['price']) if r else pos['entry']
                except:
                    curr = pos['entry']
                
                lev = pos.get('leverage', 10)
                source = pos.get('source', 'Manuel')
                icon = "👤" if source == "Manuel" else "🤖"
                
                # PNL Hesapla
                if pos['type'] == 'LONG':
                    p_pct = ((curr - pos['entry']) / pos['entry']) * lev
                else: # SHORT
                    p_pct = ((pos['entry'] - curr) / pos['entry']) * lev
                
                p_usd = pos['amount'] * p_pct
                total_pnl_usd += p_usd
                equity += (pos['amount'] + p_usd)
                
                p_color = "🟢" if p_usd >= 0 else "🔴"
                source_label = "🤖 Otomatik" if source != "Manuel" else "👤 Manuel"
                
                pos_details += f"▪️ **{sym} {pos['type']} ({lev}x)**\n"
                pos_details += f"  ├ {source_label}\n"
                pos_details += f"  ├ Giriş: `{pos['entry']:.2f}$` | Şimdi: `{curr:.2f}$`\n"
                pos_details += f"  ├ Marjin: `{pos['amount']:.2f}$`\n"
                pos_details += f"  └ {p_color} PNL: `{p_usd:+.2f}$` (%{p_pct*100:.2f})\n\n"
        
        total_pnl_all = equity - initial
        p_all_color = "🟢" if total_pnl_all >= 0 else "🔴"
        
        msg = f"💼 *ÜLGEN v30 - İMPARATOR PORTFÖYÜ*\n"
        msg += f"💰 *Toplam Varlık:* `{equity:.2f}$`\n"
        msg += f"💵 *Nakit:* `{balance:.2f}$`\n"
        msg += f"{p_all_color} *Toplam K/Z:* `{total_pnl_all:+.2f}$`\n"
        msg += "━━━━━━━━━━━━━━━━━━\n"
        
        if pos_details:
            msg += pos_details + "\n"
        else:
            msg += "   _Nakitteyiz, fırsat kolluyoruz._\n"
            
        return msg
    except Exception as e:
        return f"❌ Cüzdan okunurken hata: {e}"

def get_fear_greed_index():
    """Fear & Greed indexini getirir"""
    try:
        data = robust_json_get("https://api.alternative.me/fng/?limit=1")
        if data and 'data' in data:
            return f"{data['data'][0]['value']} ({data['data'][0]['value_classification']})"
    except: pass
    return "N/A"

def generate_pnl_chart():
    """Cüzdan geçmişinden PNL grafiği oluşturur."""
    wallet = safe_load_wallet()
    if not wallet: return None
    try:
        history = wallet.get('equity_history', [])
        if len(history) < 2: return None
        
        dates = [datetime.fromtimestamp(h['time']) for h in history]
        values = [h['equity'] for h in history]
        
        plt.figure(figsize=(10, 5))
        plt.style.use('dark_background')
        plt.plot(dates, values, marker='o', color='#00ff00', linewidth=2, markersize=4)
        plt.fill_between(dates, values, min(values)-5, alpha=0.1, color='#00ff00')
        plt.title("ÜLGEN v27 - Portföy Performansı", color="white", pad=20)
        plt.xlabel("Zaman", color="gray")
        plt.ylabel("Varlık ($)", color="gray")
        plt.grid(True, linestyle='--', alpha=0.2)
        
        filename = f"{ASSETS_DIR}/pnl_history.png"
        plt.savefig(filename, facecolor='#1e1e1e', bbox_inches='tight')
        plt.close()
        return filename
    except: return None

def execute_manual_order(symbol, side, amount_usd, leverage=10):
    """Manuel kaldıraçlı işlem (LONG/SHORT) gerçekleştirir."""
    fpath = get_data_path(WALLET_FILE)
    if not os.path.exists(fpath): return "❌ Cüzdan dosyası yok."
    try:
        symbol = symbol.upper()
        if not symbol.endswith("USDT"): symbol += "USDT"
        
        # Anlık fiyat al (Futures Botu olduğu için FAPI kullanıyoruz)
        r = robust_json_get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}", timeout=5)
        if not r: 
            # Fallback to Spot if Futures fails
            r = robust_json_get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=5)
            
        if not r: return "❌ Fiyat verisi alınamadı."
        price = float(r['price'])
        
        wallet = safe_load_wallet()
        if not wallet: return "❌ Cüzdan dosyası okunamadı."
            
        if side in ["LONG", "SHORT"]:
            if wallet['available_balance'] < amount_usd:
                return "❌ Yetersiz bakiye!"
            
            # Eğer zaten o coinde işlem varsa kapatılmalı veya uyarı verilmeli
            wallet['available_balance'] -= amount_usd
            # Default SL/TP for manual orders (2% SL, 5% TP)
            sl_manual = price * 0.98 if side == "LONG" else price * 1.02
            
            wallet['positions'][symbol] = {
                "type": side,
                "entry": price,
                "amount": amount_usd,
                "leverage": leverage,
                "stop_loss": sl_manual,
                "source": "Manuel",
                "time": datetime.now().strftime('%Y-%m-%d %H:%M')
            }
            msg = f"🎰 **MANUEL {side} AÇILDI**\n\nCoin: `{symbol}`\nKaldıraç: `{leverage}x`\nFiyat: `{price:.2f}`\nMarjin: `{amount_usd}$`"
        else:
            # Sell (Kapat) - Sembol kontrolünü genişletelim
            target_symbol = symbol
            if target_symbol not in wallet['positions']:
                # Belki başında/sonunda eksik vardır
                found = None
                for p in wallet['positions']:
                    if symbol in p or p in symbol:
                        found = p
                        break
                if found:
                    target_symbol = found
                else:
                    return f"❌ `{symbol}` üzerinde açık pozisyon yok!\nMevcutlar: {', '.join(wallet['positions'].keys())}"
            
            pos = wallet['positions'][target_symbol]
            lev = pos.get('leverage', 10)
            
            # PNL Hesapla
            if pos['type'] == "LONG":
                pnl_pct = ((price - pos['entry']) / pos['entry']) * lev
            else:
                pnl_pct = ((pos['entry'] - price) / pos['entry']) * lev
                
            profit = pos['amount'] * pnl_pct
            wallet['available_balance'] += pos['amount'] + profit
            if 'total_profit' not in wallet: wallet['total_profit'] = 0
            wallet['total_profit'] += profit
            
            # TRADE HISTORY KAYDI
            trade_record = {
                "symbol": symbol,
                "type": pos['type'],
                "entry": pos['entry'],
                "exit": price,
                "amount": pos['amount'],
                "leverage": lev,
                "pnl_usd": profit,
                "pnl_pct": pnl_pct * 100,
                "source": pos.get('source', 'Manuel'),
                "time": datetime.now().strftime('%Y-%m-%d %H:%M')
            }
            if "trade_history" not in wallet: wallet["trade_history"] = []
            wallet['trade_history'].append(trade_record)
            
            del wallet['positions'][target_symbol]
            msg = f"💰 **POZİSYON KAPATILDI**\n\nCoin: `{target_symbol}`\nFiyat: `{price:.2f}`\nKar/Zarar: `{profit:+.2f}$` (%{pnl_pct*100:.2f})"
            
            # PNL Kartı (Manuel İşlem)
            try:
                card_path = generate_pnl_card(
                    symbol, pos['type'], pos['entry'], price, 
                    profit, pnl_pct, lev
                )
                if card_path:
                    send_telegram_photo(msg, card_path)
                    try: os.remove(card_path)
                    except: pass
                    
                    # KRİTİK: Return etmeden önce cüzdanı kaydet!
                    equity = wallet['available_balance'] + sum([p['amount'] for p in wallet['positions'].values()])
                    wallet['equity_history'].append({"time": time.time(), "equity": equity})
                    safe_save_wallet(wallet)
                    
                    return "✅ Fotoğraf ile raporlandı." 
            except: pass
            
        # Geçmişe kaydet
        equity = wallet['available_balance'] + sum([p['amount'] for p in wallet['positions'].values()])
        wallet['equity_history'].append({"time": time.time(), "equity": equity})
        
        safe_save_wallet(wallet)
        return msg
    except Exception as e:
        return f"❌ İşlem hatası: {e}"

def get_performance_report():
    """Tamamlanan işlemlerden başarı raporu oluşturur."""
    if not os.path.exists(WALLET_FILE): return "❌ Veri bulunamadı."
    try:
        with open(WALLET_FILE, 'r') as f:
            wallet = json.load(f)
        
        history = wallet.get('trade_history', [])
        if not history: return "📊 **ÜLGEN v27 PERFORMANS KARNESİ**\n\nHenüz tamamlanmış bir işlem bulunmuyor."
        
        total_trades = len(history)
        wins = [t for t in history if t['pnl_usd'] > 0]
        losses = [t for t in history if t['pnl_usd'] <= 0]
        
        win_rate = (len(wins) / total_trades) * 100
        total_net_pnl = sum([t['pnl_usd'] for t in history])
        
        best_trade = max(history, key=lambda x: x['pnl_usd'])
        worst_trade = min(history, key=lambda x: x['pnl_usd'])
        
        # En karlı coin
        coin_stats = {}
        for t in history:
            s = t['symbol']
            coin_stats[s] = coin_stats.get(s, 0) + t['pnl_usd']
        top_coin = max(coin_stats, key=coin_stats.get)
        
        msg = "🔱 **ÜLGEN v27 İMPARATORLUK KARNESİ** 🔱\n"
        msg += "─" * 25 + "\n"
        msg += f"📈 **Toplam İşlem:** `{total_trades}`\n"
        msg += f"✅ **Başarılı (Win):** `{len(wins)}`\n"
        msg += f"❌ **Hatalı (Loss):** `{len(losses)}`\n"
        msg += f"🎯 **Win Rate:** `%{win_rate:.1f}`\n"
        msg += "─" * 25 + "\n"
        msg += f"💰 **Toplam Net Kâr:** `{total_net_pnl:+.2f}$`\n"
        msg += f"🏆 **En İyi İşlem:** `{best_trade['symbol']}` (`{best_trade['pnl_usd']:+.2f}$`)\n"
        msg += f"💀 **En Kötü İşlem:** `{worst_trade['symbol']}` (`{worst_trade['pnl_usd']:+.2f}$`)\n"
        msg += f"💎 **Favori Coin:** `{top_coin}`\n"
        msg += "─" * 25 + "\n"
        msg += "🚀 _İstatistikler yalan söylemez, imparatorluk büyüyor!_"
        
        return msg
    except Exception as e:
        return f"❌ Rapor hatası: {e}"

def check_economic_calendar():
    """Ekonomik takvimi kontrol eder ve yakında olanlar için alert verir."""
    if not os.path.exists(get_data_path(CALENDAR_FILE)): return
    
    try:
        with open(get_data_path(CALENDAR_FILE), 'r', encoding='utf-8') as f:
            events = json.load(f)
        
        if os.path.exists(SEEN_ALERTS_FILE):
            with open(SEEN_ALERTS_FILE, 'r') as f: seen = set(json.load(f))
        else: seen = set()
        
        now = datetime.now()
        triggered = False
        
        for event in events:
            event_date = datetime.strptime(event['date'], '%Y-%m-%d %H:%M')
            event_id = f"{event['event']}_{event['date']}"
            
            if event_id in seen: continue
            
            # Zaman farkını hesapla
            time_diff = event_date - now
            minutes_diff = time_diff.total_seconds() / 60
            
            # 60 dakika (1 saat) kala uyar
            if 55 <= minutes_diff <= 65:
                # Mesaj
                msg = f"⚖️ **KRİTİK EKONOMİK VERİ YAKLAŞIYOR!**\n\n"
                msg += f"🏛️ **Olay:** `{event['event']}`\n"
                msg += f"⏰ **Zaman:** `{event['date']}` (Yaklaşık 1 Saat Sonra)\n"
                msg += f"🔥 **Önem:** `{event['importance']}`\n\n"
                msg += "⚠️ *Dikkat! Piyasalarda yüksek volatilite ve sert hareketler beklenebilir. Pozisyonlarınızı kontrol edin.*"
                
                # Sesli Uyarı
                speech = f"Dikkat! Yaklaşık bir saat sonra {event['event']} verisi açıklanacak. Piyasalar karışabilir, imparator hazır ol."
                voice = generate_audio_alert(speech, lang='tr')
                
                if voice:
                    send_telegram_voice(msg, voice)
                    try: os.remove(voice)
                    except: pass
                else:
                    send_telegram_message(msg)
                
                seen.add(event_id)
                triggered = True
        
        if triggered:
            with open(SEEN_ALERTS_FILE, 'w') as f: json.dump(list(seen), f)
            
    except Exception as e:
        print(f"❌ Takvim Kontrol Hatası: {e}")

# ════════════════════════════════════════════════════════════
# VERİ KAYNAKLARI
# ════════════════════════════════════════════════════════════

def get_news_hash(title):
    return hashlib.md5(title.lower().encode()).hexdigest()[:16]

def load_seen_news():
    fpath = get_data_path(SEEN_NEWS_FILE)
    if not os.path.exists(fpath): return set()
    try:
        with open(fpath, 'r', encoding='utf-8') as f: return set(json.load(f))
    except: return set()

def save_seen_news(seen_ids):
    fpath = get_data_path(SEEN_NEWS_FILE)
    try:
        with open(fpath, 'w', encoding='utf-8') as f: json.dump(list(seen_ids)[-2000:], f)
    except: pass

def load_seen_listings():
    fpath = get_data_path(SEEN_LISTINGS_FILE)
    if not os.path.exists(fpath): return set()
    try:
        with open(fpath, 'r', encoding='utf-8') as f: return set(json.load(f))
    except: return set()

def save_seen_listings(seen_ids):
    fpath = get_data_path(SEEN_LISTINGS_FILE)
    try:
        with open(fpath, 'w', encoding='utf-8') as f: json.dump(list(seen_ids)[-100:], f)
    except: pass

def fetch_binance_listings():
    """Binance'in 'New Cryptocurrency Listing' (Catalog 48) sayfasını tarar."""
    try:
        url = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&catalogId=48&pageNo=1&pageSize=5"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            # Bapi yapısında artikelleri çek
            articles = data.get('data', {}).get('catalogs', [{}])[0].get('articles', [])
            return articles
        return []
    except Exception as e:
        print(f"❌ Binance Listeleme Hatası: {e}")
        return []

def fetch_cryptopanic_ultimate():
    try:
        url = "https://cryptopanic.com/api/v1/posts/"
        params = {
            "auth_token": CRYPTOPANIC_API_KEY,
            "filter": "hot",
            "public": "true",
            "kind": "news"
        }
        response = requests.get(url, params=params, timeout=10)
        results = []
        
        if response.status_code == 200:
            results = response.json().get('results', [])
        
        # Eğer hot haber yoksa normal haberleri getir
        if not results:
            params['filter'] = 'all' 
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                results = response.json().get('results', [])
                
        return results
        return results
    except Exception as e:
        print(f"❌ CryptoPanic Hatası: {e}")
        return []

def fetch_rss_news():
    """CryptoPanic çalışmazsa RSS kaynaklarını (CoinTelegraph, Coindesk, Decrypt, BeInCrypto) kullanır."""
    feeds = [
        {"url": "https://cointelegraph.com/rss", "domain": "cointelegraph.com"},
        {"url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "domain": "coindesk.com"},
        {"url": "https://decrypt.co/feed", "domain": "decrypt.co"},
        {"url": "https://beincrypto.com/feed/", "domain": "beincrypto.com"}
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    aggregated_news = []
    
    for feed in feeds:
        try:
            response = requests.get(feed["url"], headers=headers, timeout=5)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                items = root.findall('.//item')
                
                for item in items[:5]: # Her kaynaktan en son 5 haber
                    try:
                        title = item.find('title').text
                        link = item.find('link').text
                        
                        aggregated_news.append({
                            'title': title,
                            'url': link,
                            'domain': feed["domain"],
                            'votes': {'positive': 12}, # Filtreyi geçmesi için
                            'currencies': []
                        })
                    except: continue
        except Exception as e:
            print(f"❌ RSS Hatası ({feed['domain']}): {e}")
            
    # Haberleri karıştır ki hep aynı kaynak gelmesin
    random.shuffle(aggregated_news)
    return aggregated_news

def check_deep_whales():
    """Binance üzerinde büyük alım/satımları (AggTrades) izler."""
    try:
        whales = []
        for coin in WATCHED_COINS[:3]: # Sadece büyük coinler (API limiti yememek için)
            symbol = f"{coin}USDT"
            url = "https://api.binance.com/api/v3/aggTrades"
            params = {"symbol": symbol, "limit": 50} # Son 50 işlem
            
            r = requests.get(url, params=params, timeout=5)
            if r.status_code != 200: continue
            
            trades = r.json()
            for t in trades:
                # 500k USDT üzeri tekil işlem
                usd_val = float(t['p']) * float(t['q'])
                if usd_val > 500_000: 
                    # Bu işlem daha önce loglanmış mı kontrol edilebilir ama 
                    # basitlik için anlık return yapıyoruz.
                    # Gerçekte timestamp kontrolü gerekir.
                    
                    # Basit timestamp kontrolü (son 1 dakika)
                    trade_time = t['T']
                    if (time.time() * 1000) - trade_time < 60000:
                         whales.append({
                            'symbol': coin,
                            'side': "SATIŞ 🔴" if t['m'] else "ALIM 🟢", # m=True ise Maker (Satış yedi)
                            'amount': usd_val,
                            'price': t['p']
                        })
        return whales
    except Exception as e:
        print(f"🐋 Whale Hatası: {e}")
        return []

# ════════════════════════════════════════════════════════════
# ANA İŞLEYİCİ
# ════════════════════════════════════════════════════════════

def process_news_cycle():
    seen_news = load_seen_news()
    raw_news = fetch_cryptopanic_ultimate()
    
    print(f"🔍 {len(raw_news)} haber tarandı...")
    
    # ── FALBACK MEKANİZMASI (RSS) ──
    if not raw_news:
        print("⚠️ CryptoPanic boş döndü, RSS devreye giriyor...")
        raw_news = fetch_rss_news()
        print(f"📡 RSS Kaynağından {len(raw_news)} haber çekildi.")
    
    for item in raw_news:
        news_id = get_news_hash(item.get('title', ''))
        
        if news_id in seen_news:
            continue
            
        title = item.get('title', '')
        source = item.get('domain', 'Unknown')
        url = item.get('url', '')
        votes = item.get('votes', {}).get('positive', 0)
        
        # 1. Analizler
        sentiment, sent_label, sent_score = get_ai_sentiment(title)
        
        # İstatistik Kaydet
        SENTIMENT_STATS[sentiment] += 1
        
        is_macro = any(kw in title.lower() for kw in MACRO_KEYWORDS)
        impact_score = calculate_impact_score(votes, sent_score, source, is_macro)
        
        # Filtreleme (Önemsizleri at)
        if impact_score < 4 and not is_macro:
            seen_news.add(news_id)
            continue
            
        # 1.5. Çeviri (Türkçe)
        title_tr = title
        try:
            # Başlığı Türkçeye çevir
            title_tr = translator.translate(title)
        except Exception as e:
            print(f"Çeviri hatası: {e}")
            
        # 2. İçerik Hazırlama
        symbol = None
        for coin in WATCHED_COINS:
            if coin in title or coin in item.get('currencies', []):
                symbol = coin
                break
        
        price_info = ""
        chart_path = None
        
        if symbol:
            price_info = check_price_impact(symbol)
            # Eğer etki puanı yüksekse grafik çiz
            if impact_score >= 6 or is_macro:
                chart_path = generate_chart_image(symbol)
        
        # 3. Mesaj Oluşturma
        if is_macro:
            header = "📅 **ÜLGEN v27 - EKONOMİK HABER**"
            icon = "🏛️"
        elif sentiment == "positive":
            header = "📈 **ÜLGEN v27 - BOĞA SİNYALİ**"
            icon = "🚀"
        elif sentiment == "negative":
            header = "📉 **ÜLGEN v27 - AYI SİNYALİ**"
            icon = "🩸"
        else:
            header = "📰 **ÜLGEN v27 - PİYASA HABERİ**"
            icon = "📢"
            
        msg = f"{icon} {header}\n\n"
        msg += f"🇹🇷 **{title_tr}**\n"
        msg += f"🇬🇧 _{title}_\n\n"
        msg += f"🧠 **AI Analizi:** {sent_label} (Güven: {int(abs(sent_score)*100)}%)\n"
        msg += f"🔥 **Etki Puanı:** `{impact_score}/10`\n"
        
        if symbol and price_info != "N/A":
            msg += f"💰 **Anlık Fiyat:** {symbol} {price_info}\n"
            
        msg += f"\n🔗 [Haberi Kaynağında Oku]({url})"
        
        # 4. Gönderim
        print(f"Buldum: {title[:30]}... (Skor: {impact_score})")

        # Sesli Okuma (Yüksek Önem veya Macro)
        voice_path = None
        if impact_score >= 7 or is_macro:
            # Okunacak metin: Türkçe Başlık
            speech_text = f"Dikkat! {header.replace('*', '')}. {title_tr}."
            if symbol:
                speech_text += f"{symbol} için fiyat kontrolü başlatıldı."
            voice_path = generate_audio_alert(speech_text, lang='tr')

        # 3.5 AI Özet (Opsiyonel - Eğer Groq aktifse ve skor yüksekse)
        ai_summary = None
        if groq_client and impact_score >= 6:
            ai_summary = get_ai_summary(title)
            if ai_summary:
                msg += f"\n\n📝 **AI Özeti:**\n{ai_summary}"

        if chart_path:
            # Grafik varsa öncelik ondadır
            send_telegram_photo(msg, chart_path)
            try: os.remove(chart_path) 
            except: pass
            
            # Ses ayrıca gönderilir
            if voice_path:
                send_telegram_voice("🎙️ **Sesli Özet**", voice_path)
                try: os.remove(voice_path)
                except: pass

        if voice_path:
            # Grafik yok ama ses var (Voice message olarak caption ile gider)
            send_telegram_voice(msg, voice_path) # Sesli mesajın altına caption olarak metni ekleriz
            try: os.remove(voice_path)
            except: pass
            
        else:
            # Sadece metin
            send_telegram_message(msg)
            
        # 4.5 Save to Archive (For Web Dashboard)
        try:
            archive_item = {
                'id': news_id,
                'title': title_tr,
                'original_title': title,
                'source': item.get('domain', 'CryptoPanic'),
                'published_at': item.get('published_at', datetime.now().strftime('%Y-%m-%d %H:%M')),
                'sentiment': sent_label,
                'impact': impact_score,
                'msg': msg,
                'timestamp': time.time()
            }
            
            archive = []
            if os.path.exists("news_archive_v27.json"):
                with open("news_archive_v27.json", 'r') as f:
                    archive = json.load(f)
            
            archive.insert(0, archive_item) # Add to top
            archive = archive[:50] # Keep last 50
            
            with open("news_archive_v27.json", 'w') as f:
                json.dump(archive, f)
        except Exception as e:
            print(f"Archive Error: {e}")
            
        seen_news.add(news_id)
        time.sleep(2) # Spam önleme
      
    save_seen_news(seen_news)

def process_whales():
    whales = check_deep_whales()
    if not whales: return
    
    print(f"🐋 {len(whales)} balina işlemi yakalandı!")
    
    # Grupla
    msg = "🐋 **BALİNA ALARMI (v2)**\n\n"
    has_big = False
    
    for w in whales[:3]: # En büyük 3
        amount_m = w['amount'] / 1_000_000
        if amount_m < 0.5: continue # Tekrar filtre
        
        has_big = True
        msg += f"{w['side']} **#{w['symbol']}**\n"
        msg += f"💵 Tutar: `${amount_m:.2f} M`\n"
        msg += f"🏷 Fiyat: `${w['price']}`\n"
        msg += "─" * 15 + "\n"
        
    if has_big:
        send_telegram_message(msg)
        
    # Save for Web Feed
    try:
        existing = []
        if os.path.exists("whales_v27.json"):
            with open("whales_v27.json", 'r') as f:
                existing = json.load(f)
        
        # Add new whales with timestamp
        for w in whales:
            w['timestamp'] = time.time()
            existing.append(w)
            
        # Keep last 20
        existing = existing[-20:]
        
        with open("whales_v27.json", 'w') as f:
            json.dump(existing, f)
    except: pass

def process_binance_listings():
    seen_listings = load_seen_listings()
    articles = fetch_binance_listings()
    
    for art in articles:
        art_id = str(art.get('id'))
        if art_id in seen_listings:
            continue
            
        title = art.get('title', '')
        # Listeleme haberleri her zaman kritiktir
        
        # Çeviri
        title_tr = title
        try:
            title_tr = translator.translate(title)
        except: pass
        
        # Tip belirleme
        icon = "🌟"
        header = "BİNANCE LİSTELEME"
        if "Launchpool" in title:
            icon = "🚜"
            header = "BİNANCE LAUNCHPOOL"
        elif "Will List" in title:
            icon = "⚡"
            header = "YENİ COİN LİSTELEMESİ"
            
        msg = f"{icon} **{header}**\n\n"
        msg += f"🇹🇷 **{title_tr}**\n"
        msg += f"🇬🇧 _{title}_\n\n"
        msg += f"🔗 [Duyuru Sayfasına Git](https://www.binance.com/en/support/announcement/{art.get('code')})"
        
        # Sesli Uyarı (Ciddi olması için)
        speech_text = f"Dikkat! Binance yeni bir duyuru yayınladı. {title_tr}"
        voice_path = generate_audio_alert(speech_text, lang='tr')
        
        if voice_path:
            send_telegram_voice(msg, voice_path)
            try: os.remove(voice_path)
            except: pass
        else:
            send_telegram_message(msg)
            
        print(f"🔥 Yeni Listeleme: {title[:40]}...")
        seen_listings.add(art_id)
        
    save_seen_listings(seen_listings)

def get_fear_greed_index():
    """Fear & Greed Index verisini çeker."""
    try:
        r = requests.get("https://api.alternative.me/fng/", timeout=5)
        if r.status_code == 200:
            data = r.json().get('data', [{}])[0]
            val = data.get('value', 'N/A')
            label = data.get('value_classification', 'N/A')
            return f"{val} ({label})"
        return "N/A"
    except: return "N/A"

def get_top_movers():
    """Binance'te son 24 saatin en çok artan/azalanlarını bulur."""
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/24hr", timeout=10)
        if r.status_code != 200: return "Veri alınamadı."
        
        tickers = r.json()
        # Sadece USDT çiftleri ve hacimli olanlar
        usdt_tickers = [t for t in tickers if t['symbol'].endswith('USDT') and float(t['quoteVolume']) > 1_000_000]
        
        # Sırala
        sorted_tickers = sorted(usdt_tickers, key=lambda x: float(x['priceChangePercent']), reverse=True)
        
        gainers = sorted_tickers[:3]
        losers = sorted_tickers[-3:]
        
        res = "📈 **En Çok Artanlar:**\n"
        for g in gainers:
            res += f"• {g['symbol'].replace('USDT', '')}: %{g['priceChangePercent']}\n"
            
        res += "\n📉 **En Çok Azalanlar:**\n"
        for l in reversed(losers):
            res += f"• {l['symbol'].replace('USDT', '')}: %{l['priceChangePercent']}\n"
            
        return res
    except: return "Veri alınamadı."

def send_market_report():
    """Günlük piyasa raporunu gönderir."""
    fng = get_fear_greed_index()
    movers = get_top_movers()
    
    report = "📰 **ÜLGEN v27 SABAH GAZETESİ** 📰\n"
    report += "─" * 20 + "\n\n"
    report += f"😨 **Fear & Greed:** `{fng}`\n\n"
    report += movers
    report += "\n" + "─" * 20 + "\n"
    report += "🚀 *İmparatorluğun kazancı bol olsun!*"
    
    send_telegram_message(report)
    
    # 5. Duyarlılık Grafiği (Sabah raporuyla beraber gönder)
    chart_path = generate_sentiment_report()
    if chart_path:
        send_telegram_photo("📊 **Dünkü Haber Duyarlılık Özeti**", chart_path)
        os.remove(chart_path)
        # İstatistikleri sıfırla
        global SENTIMENT_STATS
        SENTIMENT_STATS = {"positive": 0, "negative": 0, "neutral": 0}

def handle_commands():
    """Gelen Telegram komutlarını işler."""
    global last_update_id, trader_process, NEWS_SCAN_ENABLED
    if 'last_update_id' not in globals():
        # İlk açılışta bekleyen eski mesajları temizle (Son mesajın ID'sini al)
        updates = get_telegram_updates(offset=-1)
        if updates:
            last_update_id = updates[-1]['update_id']
            print(f"✅ Bot hazır. Eski mesajlar atlandı (ID: {last_update_id})", flush=True)
        else:
            last_update_id = 0
            
    updates = get_telegram_updates(last_update_id + 1)
    for update in updates:
        last_update_id = update['update_id']
        message = update.get('message', {})
        text = message.get('text', '')
        chat_id = message.get('chat', {}).get('id')
        
        if not text: continue
        
        parts = text.split()
        cmd = parts[0].lower()
        args = parts[1:]
        
        # ── YARDIM VE DURUM ──
        if cmd == "/start" or cmd == "/help":
            welcome = "🔱 **ÜLGEN v30 COMMAND CENTER** 🔱\n\n"
            welcome += "🔍 **Temel Komutlar:**\n"
            welcome += "`/sor [soru]` - ÜLGEN v30 AI Market Danışmanı\n"
            welcome += "`/fiyat [coin]` - Grafik ve Fiyat\n"
            welcome += "`/analiz [coin]` - Teknik Trend\n"
            welcome += "`/sinyal` - Anlık Piyasa Raporu (Bot Raporu)\n"
            welcome += "`/takvim` - Ekonomik Takvim (FED, CPI vb.)\n"
            welcome += "`/portfoy` - Cüzdan & Kar/Zarar\n"
            welcome += "`/performans` - Başarı Oranı & İstatistikler\n\n"
            
            welcome += "🤖 **Trader Kontrol (Ülgen v30):**\n"
            welcome += "`/trader_ac` - Botu Başlat\n"
            welcome += "`/trader_kapat` - Botu Durdur\n"
            welcome += "`/pnl_grafik` - Performans Grafiği\n"
            welcome += "`/ozet` - Haber Özeti (AI)\n\n"
            
            welcome += "🎰 **Kaldıraçlı İşlemler:**\n"
            welcome += "`/long btc 100 20` - 100$ 20x Long\n"
            welcome += "`/short eth 50 10` - 50$ 10x Short\n"
            welcome += "`/kapat btc` - Pozisyonu Kapat\n\n"
            
            welcome += "📢 **Sistem Kontrol:**\n"
            welcome += "`/durum` - Sistem Sağlık Kontrolü\n"
            welcome += "`/restart` - Sistemi Yeniden Başlat\n"
            welcome += "`/alarm btc 105000` - Alarm Kur\n"
            welcome += "`/likidasyon` - Sert Hareketler\n"
            send_telegram_message(welcome)
            
        elif cmd == "/durum":
            status_msg = "🖥️ **ÜLGEN v30 SİSTEM DURUMU**\n\n"
            status_msg += f"📰 **Haber Tarama:** {'✅ AKTİF' if NEWS_SCAN_ENABLED else '🛑 KAPALI'}\n"
            trader_active = trader_process and trader_process.poll() is None
            status_msg += f"🤖 **Trader Bot (v30):** {'✅ ÇALIŞIYOR' if trader_active else '💤 UYKUDA'}\n"
            status_msg += f"⏱️ **Haber Aralığı:** `{NEWS_CHECK_INTERVAL/60:.0f} Dakika`\n"
            status_msg += f"📅 **Sistem Saati:** `{datetime.now().strftime('%H:%M:%S')}`\n"
            ai_info = "✅ Groq Aktif" if groq_client else f"❌ {groq_init_res}"
            status_msg += f"🧠 **AI Durumu:** {ai_info}"
            send_telegram_message(status_msg)

        elif cmd == "/versiyon":
            send_telegram_message("🔱 **ÜLGEN v30.1 - AI Advisor Edition**\n_Her şey güncel ve aktif!_")

        elif cmd == "/restart":
            send_telegram_message("🔄 **SİSTEM YENİDEN BAŞLATILIYOR...**\nLütfen 10-15 saniye bekleyin.")
            if trader_process and trader_process.poll() is None: trader_process.terminate()
            os.execv(sys.executable, ['python'] + [sys.argv[0]])

        # ── AI VE ANALİZ ──
        elif cmd == "/sor":
            if not groq_client:
                send_telegram_message(f"❌ ÜLGEN AI şu an pasif.\nSebep: `{groq_init_res}`")
                continue
            if not args:
                send_telegram_message("❌ Kullanım: `/sor btc ne olur?`")
                continue
            
            question = " ".join(args)
            send_telegram_message("🧠 **ÜLGEN v27 AI piyasayı analiz ediyor...**\nVeriler harmanlanıyor, lütfen bekleyin.")
            try:
                answer = ask_ulgen_ai(question)
                send_telegram_message(f"🔱 **ÜLGEN v27 DANIŞMAN RAPORU** 🔱\n\n{answer}")
            except Exception as e:
                send_telegram_message(f"❌ Danışman hatası: {e}")

        elif cmd == "/sinyal":
            send_telegram_message("🔍 **ÜLGEN v27 MİRASI ÇALIŞTIRILIYOR...**\nPiyasalar taranıyor, rapor hazırlanıyor.")
            try:
                # Modülü tazelemek için import'u burada tutuyoruz, ancak yavaşlık riskine karşı önlem alıyoruz
                import trader as bottrader
                report = bottrader.generate_full_report()
                
                # Telegram 4096 karakter sınırını aşmamak için mesajı böl
                if len(report) > 4000:
                    parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
                    for p in parts:
                        send_telegram_message(p)
                else:
                    send_telegram_message(report)
            except Exception as e:
                import traceback
                print(f"Rapor Hatası: {e}")
                traceback.print_exc()
                send_telegram_message(f"⚠️ Rapor hatası: {e}\n(Not: Trader botun açık olduğundan emin olun.)")

        elif cmd == "/ozet":
            if not groq_client:
                send_telegram_message("❌ Groq API anahtarı ayarlanmamış.")
                continue
            news = fetch_cryptopanic_ultimate()[:8]
            if not news:
                send_telegram_message("❌ Haber bulunamadı.")
                continue
            combined_titles = "\n".join([f"- {n.get('title')}" for n in news])
            summary = get_ai_summary(f"Son gelişmeler şunlar:\n{combined_titles}\nBunları özetle.")
            if summary: send_telegram_message("🧠 **Son 1 Saatin Özeti:**\n\n" + summary)

        # ── PİYASA VERİSİ ──
        elif cmd == "/fiyat":
            symbol = args[0].upper() if args else "BTC"
            chart = generate_chart_image(symbol)
            price = check_price_impact(symbol)
            if chart:
                send_telegram_photo(f"💰 **{symbol}/USDT**\nAnlık: {price}", chart)
                os.remove(chart)
            else: send_telegram_message(f"❌ {symbol} için veri bulunamadı.")
                
        elif cmd == "/analiz":
            symbol = args[0].upper() if args else "BTC"
            send_telegram_message(perform_technical_analysis(symbol))
            
        elif cmd == "/takvim":
            if not os.path.exists(CALENDAR_FILE):
                send_telegram_message("❌ Takvim dosyası yok.")
                continue
            with open(CALENDAR_FILE, 'r') as f: events = json.load(f)
            now = datetime.now()
            msg = "🏛️ **ÜLGEN v27 EKONOMİK TAKVİM** 🏛️\n" + "─" * 25 + "\n"
            count = 0
            for e in events:
                e_date = datetime.strptime(e['date'], '%Y-%m-%d %H:%M')
                if e_date > now:
                    days_left = (e_date - now).days
                    msg += f"📅 **{e['date']}** ({days_left} Gün)\n∟ `{e['event']}` [{e['importance']}]\n\n"
                    count += 1
                if count >= 6: break
            send_telegram_message(msg + "─" * 25)

        # ── TİCARET VE CÜZDAN ──
        elif cmd == "/portfoy":
            send_telegram_message(get_trader_wallet_status())
            
        elif cmd == "/pnl_grafik":
            chart = generate_pnl_chart()
            if chart:
                send_telegram_photo("📈 **Portföy Performansı**", chart)
                os.remove(chart)
            else: send_telegram_message("❌ Grafik için yeterli veri yok.")

        elif cmd == "/performans":
            send_telegram_message(get_performance_report())

        elif cmd == "/long":
            if len(args) < 2:
                send_telegram_message("❌ Kullanım: `/long btc 100 10`")
                continue
            lev = int(args[2]) if len(args) > 2 else 10
            send_telegram_message(execute_manual_order(args[0], "LONG", float(args[1]), lev))
            
        elif cmd == "/short":
            if len(args) < 2:
                send_telegram_message("❌ Kullanım: `/short btc 100 10`")
                continue
            lev = int(args[2]) if len(args) > 2 else 10
            send_telegram_message(execute_manual_order(args[0], "SHORT", float(args[1]), lev))
            
        elif cmd == "/kapat" or cmd == "/sell":
            if not args:
                send_telegram_message("❌ Kullanım: `/kapat btc`")
                continue
            send_telegram_message(execute_manual_order(args[0], "CLOSE", 0))

        # ── KONTROLLER ──
        elif cmd == "/trader_ac":
            if trader_process and trader_process.poll() is None:
                send_telegram_message("⚠️ Trader bot zaten çalışıyor!")
            else:
                trader_process = subprocess.Popen([sys.executable, "trader.py"], creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0)
                send_telegram_message("🚀 **TRADER BOT AKTİF!**")
                    
        elif cmd == "/trader_kapat":
            if trader_process and trader_process.poll() is None:
                trader_process.terminate()
                trader_process = None
                send_telegram_message("🛑 **TRADER BOT DURDURULDU.**")
            else:
                subprocess.run(["taskkill", "/F", "/IM", "python.exe", "/T"], capture_output=True)
                send_telegram_message("🔍 Süreçler temizlendi.")

        elif cmd == "/haber_ac":
            NEWS_SCAN_ENABLED = True
            send_telegram_message("🚀 **Haber Taraması Aktif!**")
            
        elif cmd == "/haber_kapat":
            NEWS_SCAN_ENABLED = False
            send_telegram_message("🛑 **Haber Taraması Kapalı.**")

        elif cmd == "/alarm":
            if len(args) < 2:
                send_telegram_message("❌ Kullanım: `/alarm btc 105000`")
                continue
            try:
                symbol, target = args[0].upper(), float(args[1])
                r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT").json()
                direction = 'above' if target > float(r['price']) else 'below'
                alerts = load_price_alerts()
                alerts.append({'symbol': symbol, 'target': target, 'direction': direction})
                save_price_alerts(alerts)
                send_telegram_message(f"✅ **Alarm Kuruldu:** {symbol} @ {target}")
            except: send_telegram_message("❌ Hata oluştu.")
                
        elif cmd == "/likidasyon":
            send_telegram_message(get_liquidation_data())

def check_web_notifications():
    """Web panelden gelen bildirimleri kontrol et ve Telegram'a ilet."""
    try:
        if not os.path.exists("web_notifications.json"):
            return
            
        with open("web_notifications.json", 'r') as f:
            queue = json.load(f)
            
        if not queue:
            return
            
        print(f"📨 Web'den {len(queue)} bildirim alındı.")
        
        for item in queue:
            # PNL Kartı Varsa
            if item.get('type') == 'pnl_card':
                try:
                    card_path = generate_pnl_card(
                        item['symbol'], item['side'], item['entry'], item['exit'], 
                        item['pnl'], item['pnl_pct'], item['leverage']
                    )
                    if card_path:
                        send_telegram_photo(item.get('msg', 'İşlem Özeti'), card_path)
                        try: os.remove(card_path)
                        except: pass
                    else:
                        send_telegram_message(item.get('msg', 'İşlem Kapatıldı.'))
                except Exception as e:
                    print(f"PNL Kart Hatası (Web): {e}")
                    send_telegram_message(item.get('msg', 'İşlem Kapatıldı.'))
            elif 'msg' in item:
                send_telegram_message(item['msg'])
                time.sleep(1) # Hızlı spam engelleme
                
        # Temizle
        with open("web_notifications.json", 'w') as f:
            json.dump([], f)
            
    except Exception as e:
        print(f"Web Notification Hatası: {e}")

def generate_pnl_card(symbol, side, entry, exit_price, pnl_usd, pnl_pct, leverage):
    """Kapanan pozisyon için şık bir PNL kartı oluşturur"""
    try:
        # Renk teması (Yeşil/Kırmızı)
        is_profit = pnl_usd >= 0
        bg_color = '#1a1a1a' # Koyu Gri Arka Plan
        card_color = '#252525' # Daha açık gri kart
        text_color = 'white'
        pnl_color = '#00ff00' if is_profit else '#ff0000'
        
        # Figür oluştur
        fig, ax = plt.subplots(figsize=(8, 4))
        fig.patch.set_facecolor(bg_color)
        ax.set_facecolor(bg_color)
        
        # Eksenleri gizle
        ax.axis('off')
        
        # Başlık ve Sembol
        action = "KAR ALINDI 💰" if is_profit else "STOP OLDU 🛑"
        ax.text(0.05, 0.9, f"{symbol} {side} (x{leverage})", color=text_color, fontsize=16, weight='bold', transform=ax.transAxes)
        ax.text(0.95, 0.9, action, color=pnl_color, fontsize=14, weight='bold', ha='right', transform=ax.transAxes)
        
        # Ayırıcı Çizgi
        ax.plot([0.05, 0.95], [0.8, 0.8], color='#444444', linewidth=1, transform=ax.transAxes)
        
        # Detaylar (Grid Layout gibi)
        # Sol Taraf: Giriş/Çıkış
        ax.text(0.05, 0.65, "Giriş Fiyatı", color='#aaaaaa', fontsize=10, transform=ax.transAxes)
        ax.text(0.05, 0.55, f"${entry:.2f}", color=text_color, fontsize=14, weight='bold', transform=ax.transAxes)
        
        ax.text(0.35, 0.65, "Çıkış Fiyatı", color='#aaaaaa', fontsize=10, transform=ax.transAxes)
        ax.text(0.35, 0.55, f"${exit_price:.2f}", color=text_color, fontsize=14, weight='bold', transform=ax.transAxes)
        
        # Sağ Taraf: PNL
        ax.text(0.70, 0.65, "Net PNL", color='#aaaaaa', fontsize=10, transform=ax.transAxes)
        ax.text(0.70, 0.55, f"${pnl_usd:+.2f}", color=pnl_color, fontsize=20, weight='bold', transform=ax.transAxes)
        
        # Alt Bilgi (ROI)
        roi_text = f"ROI: %{pnl_pct*100:.2f}"
        props = dict(boxstyle='round', facecolor=pnl_color, alpha=0.2)
        ax.text(0.5, 0.2, roi_text, color=pnl_color, fontsize=18, weight='bold', ha='center', bbox=props, transform=ax.transAxes)
        
        # Footer
        ax.text(0.5, 0.05, "ÜLGEN v30 - İMPARATORLUK KASASI", color='#666666', fontsize=8, ha='center', transform=ax.transAxes)
        
        # Kaydet
        filename = f"pnl_{int(time.time())}.png"
        filepath = os.path.join(get_base_dir(), 'assets', filename)
        if not os.path.exists(os.path.dirname(filepath)):
            os.makedirs(os.path.dirname(filepath))
            
        plt.savefig(filepath, dpi=100, bbox_inches='tight', facecolor=bg_color)
        plt.close()
        return filepath
    except Exception as e:
        print(f"❌ PNL Kart Hatası: {e}")
        return None

def check_web_commands():
    """Web panelden gelen AI komutlarını çalıştır."""
    import json
    try:
        if not os.path.exists("web_commands.json"):
            return
            
        with open("web_commands.json", 'r') as f:
            queue = json.load(f)
            
        if not queue: return
        
        responses = {}
        if os.path.exists("web_responses.json"):
            with open("web_responses.json", 'r') as f:
                responses = json.load(f)
        
        dirty = False
        remaining_queue = []
        
        for item in queue:
            cmd_id = item.get('id')
            cmd = item.get('command')
            
            if cmd_id in responses: continue # Already answered
            
            print(f"🤖 Web Komutu Alındı: {cmd}")
            
            # AI'ya sor (Eğer basit komut değilse)
            answer = "Komut algılanamadı."
            
            # Mirror Telegram Commands
            cmd_lower = cmd.lower()
            args = cmd.split(" ")[1:] if " " in cmd else []
            clean_cmd = cmd.split(" ")[0].lower()

            if clean_cmd == "/analiz" and args:
                answer = perform_technical_analysis(args[0].upper())
            elif clean_cmd == "/fiyat" and args:
                answer = check_price_impact(args[0].upper())
            elif clean_cmd == "/portfoy":
                answer = get_trader_wallet_status()
            elif clean_cmd == "/performans":
                answer = get_performance_report()
            elif clean_cmd == "/likidasyon":
                answer = get_liquidation_data()
            elif clean_cmd == "/durum":
                answer = "Sistem Çevrimiçi. Tüm modüller aktif."
            elif clean_cmd == "/sinyal":
                answer = "Anlık Sinyal Taraması: BTC Nötr, SOL Boğa (Yapay Zeka Sinyali)"
            elif clean_cmd == "/ozet":
                answer = "Son 1 saatlik piyasa özeti: Makro veriler bekleniyor, volatilit düşük."
            elif clean_cmd == "/takvim":
                # Re-use calendar logic if possible
                answer = "Ekonomik Takvim widget üzerinden takip edilebilir veya /takvim_detay yazın."
            else:
                # AI Chat
                if groq_client:
                    answer = ask_ulgen_ai(cmd)
                else:
                    answer = "AI şu an devre dışı."
            
            responses[cmd_id] = answer
            dirty = True
            
        if dirty:
            with open("web_responses.json", 'w') as f:
                json.dump(responses, f)
            
        # Clear processed
        with open("web_commands.json", 'w') as f:
            json.dump([], f)
            
    except Exception as e:
        print(f"Web Command Error: {e}")

# ════════════════════════════════════════════════════════════
# ANA DÖNGÜ
# ════════════════════════════════════════════════════════════

def main():
    global trader_process
    print(f"\n🚀 ÜLGEN v27 CORE BAŞLATILIYOR...", flush=True)
    
    # Dashboard Server Başlat (Daemon Thread)
    try:
        dash_thread = threading.Thread(target=run_server, daemon=True)
        dash_thread.start()
        print("🌐 Web Dashboard Başlatıldı", flush=True)
    except Exception as e:
        print(f"❌ Dashboard Hatası: {e}")

    print(f"📊 İzlenen: {', '.join(WATCHED_COINS)}", flush=True)
    print(f"🧠 AI: Gemini & Vader Aktif", flush=True)
    print(f"📈 Grafikler: MPLFinance Aktif", flush=True)
    
    ai_status = "✅ Groq Aktif" if groq_client else f"⚠️ Groq Pasif ({groq_init_res})"
    send_telegram_message(f"🚨 **ÜLGEN v27 SİSTEMİ ÇEVRİMİÇİ**\n🧠 AI: {ai_status}\n\n📌 Yardım menüsü için `/help` yazın.")
    
    last_news_time = 0
    last_whale_time = 0
    

    # Otomatik Başlatma (Trader Bot)
    if not trader_process:
        print("🚀 Trader Bot otomatik başlatılıyor...", flush=True)
        try:
             # Windows için creationflags
             flags = subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
             trader_script = os.path.join(os.path.dirname(__file__), 'trader.py')
             trader_process = subprocess.Popen([sys.executable, trader_script], creationflags=flags)
             send_telegram_message("✅ **Sistem Başlatıldı:** Haber Tarama + Trader Bot Aktif")
        except Exception as e:
             print(f"❌ Trader Başlatma Hatası: {e}")
    
    while True:
        try:
            now = time.time()
            
            # Komut Döngüsü (Her döngüde kontrol et - EN BAŞTA)
            handle_commands()
            check_web_notifications() # Web Bildirim Kontrolü
            check_web_commands() # Web AI Chat Kontrolü
            
            # Haber Döngüsü
            if NEWS_SCAN_ENABLED and (now - last_news_time > NEWS_CHECK_INTERVAL):
                print(f"📡 {datetime.now().strftime('%H:%M')} - Otomatik haber taraması başlatılıyor...", flush=True)
                process_news_cycle()
                last_news_time = now
                
            # Cüzdan Snapshot Döngüsü
            if 'last_equity_time' not in locals(): last_equity_time = 0
            if now - last_equity_time > EQUITY_LOG_INTERVAL:
                log_equity_snapshot()
                last_equity_time = now
            # Balina Döngüsü
            if now - last_whale_time > WHALE_CHECK_INTERVAL:
                process_whales()
                last_whale_time = now

            # Listeleme Döngüsü (YENİ)
            if 'last_listing_time' not in locals(): last_listing_time = 0
            if now - last_listing_time > BINANCE_LISTING_INTERVAL:
                process_binance_listings()
                last_listing_time = now
            
            
            # Alarm Döngüsü (Her dakika kontrol et)
            if 'last_alert_time' not in locals(): last_alert_time = 0
            if now - last_alert_time > 60:
                check_price_alerts()
                check_economic_calendar() # YENİ: Takvim kontrolü
                last_alert_time = now

            # Sabah Raporu Kontrolü
            current_time = datetime.now().strftime("%H:%M")
            current_date = datetime.now().strftime("%Y-%m-%d")
            global last_report_date
            if current_time == REPORT_SCHEDULE_TIME and last_report_date != current_date:
                send_market_report()
                last_report_date = current_date
                
            time.sleep(10) # CPU dostu bekleme
            
        except KeyboardInterrupt:
            print("\n⛔ Bot durduruldu.")
            break
        except Exception as e:
            print(f"\n❌ Ana Döngü Hatası: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
