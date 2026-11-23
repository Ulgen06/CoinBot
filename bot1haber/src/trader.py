import requests
import pandas as pd
import numpy as np
import time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime
import os
import json
import re 
import logging

# Ensure logs directory exists
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    filename=os.path.join(log_dir, "trader_v2.log"),
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)
logging.info("Trader module initialized") 

from env_loader import load_env
load_env()

# ================== AYARLAR ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "@Ulgentrader")
COINS = ["BTCUSDT", "ETHUSDT", "TAOUSDT"] 
TIMEFRAMES = ["15m", "1h", "4h", "1d", "1M"] 

# İMPARATORLUK HAZİNESİ
WALLET_FILE = "wallet.json"
INITIAL_BALANCE = 1500 
LEVERAGE = 10
TARGET_COIN = "TAOUSDT" 

def get_base_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_data_path(filename):
    return os.path.join(get_base_dir(), 'data', filename)

# ================== YARDIMCI FONKSİYONLAR ==================
def robust_json_get(url, params=None, timeout=10):
    """API'den güvenli bir şekilde JSON çeker, hata olursa None döner"""
    try:
        r = requests.get(url, params=params, timeout=timeout)
        if r.status_code == 200:
            try:
                return r.json()
            except json.JSONDecodeError:
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
    except Exception as e:
        print(f"❌ Kayıt Hatası: {e}")
        if os.path.exists(lock_path): os.remove(lock_path)
        return False
# ================== TELEGRAM FONKSİYONLARI ==================
def send_telegram_photo(photo_path, caption):
    """Grafik görselini Telegram'a gönderir"""
    try:
        with open(photo_path, 'rb') as f:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", 
                data={'chat_id': CHAT_ID, 'caption': caption, 'parse_mode': 'Markdown'}
            )
            print(f"✅ Foto Gönderildi: {photo_path}")
    except Exception as e:
        print(f"❌ Foto Gönderilemedi: {e}")

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
    except Exception as e: 
        print(f"Görsel gönderme hatası: {e}")

def send_telegram_message(message):
    """Mesaj gönderir, hata olursa HTML ile tekrar dener"""
    try:
        logging.info(f"Sending Trader message: {message[:50]}...")
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
            json={'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
        )
        logging.info("Trader message sent.")
    except Exception as e: 
        print(f"Markdown hatası, HTML deneniyor: {e}")
        logging.warning(f"Markdown failed, trying HTML: {e}")
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                json={'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
            )
        except:
            print("Mesaj gönderilemedi!")
# ================== CÜZDAN YÖNETİMİ ==================
def get_wallet_status(current_prices, idle_reason=""):
    """Cüzdan durumunu hesaplar ve raporlar"""
    wallet = safe_load_wallet()
    if not wallet:
        wallet = {
            "initial_balance": INITIAL_BALANCE, 
            "available_balance": INITIAL_BALANCE, 
            "positions": {}, 
            "total_profit": 0,
            "equity_history": []
        }
        safe_save_wallet(wallet)
    
    available = wallet['available_balance']
    margin_used = 0
    unrealized_pnl = 0
    pos_details = ""
    
    # Açık pozisyon varsa PNL hesapla
    for symbol, pos in wallet['positions'].items():
        curr = current_prices.get(symbol)
        
        # Eğer fiyat listede yoksa (Manuel açılan farklı bir coin olabilir) API'den çek
        if curr is None:
            try:
                p_data = robust_json_get(
                    "https://fapi.binance.com/fapi/v1/ticker/price", 
                    params={'symbol': symbol}
                )
                curr = float(p_data['price']) if p_data and 'price' in p_data else pos['entry']
            except:
                curr = pos['entry']
        
        # Kar/Zarar Hesaplama (Kaldıraçlı)
        if pos['type'] == 'LONG':
            pnl_pct = ((curr - pos['entry']) / pos['entry']) * LEVERAGE
        else:  # SHORT
            pnl_pct = ((pos['entry'] - curr) / pos['entry']) * LEVERAGE
            
        pnl_usd = pos['amount'] * pnl_pct
        
        margin_used += pos['amount']
        unrealized_pnl += pnl_usd
        
        icon = "🟢" if pnl_usd > 0 else "🔴"
        source = pos.get('source', '👤 Manuel')
        if source == "Otomatik": source = "🤖 Otomatik"
        
        # Hedef Seviyeleri (Stratejiye göre)
        tp1 = pos['entry'] * (1.03 if pos['type'] == 'LONG' else 0.97)
        tp2 = pos['entry'] * (1.20 if pos['type'] == 'LONG' else 0.80)
        sl = pos.get('stop_loss', 0)
        
        pos_details += f"   ⚡ *{symbol}* {pos['type']} (x{LEVERAGE})\n"
        pos_details += f"   ├ {source}\n"
        pos_details += f"   ├ *Giriş:* `{pos['entry']:.2f}$` | *Şimdi:* `{curr:.2f}$`\n"
        pos_details += f"   ├ 🎯 *TP1 (%3):* `{tp1:.2f}$` | *TP2 (%20):* `{tp2:.2f}$`\n"
        pos_details += f"   ├ 🛑 *STOP:* `{sl:.2f}$`\n"
        pos_details += f"   ├ 💸 *Marjin:* `{pos['amount']:.2f}$`\n"
        pos_details += f"   └ {icon} *PNL:* `{pnl_usd:+.2f}$` (%{pnl_pct*100:.2f})\n\n"

    equity = available + margin_used + unrealized_pnl
    total_pnl = equity - wallet['initial_balance']
    pnl_color = "🟢" if total_pnl >= 0 else "🔴"
    
    msg = f"💼 *ÜLGEN v30 - İMPARATOR PORTFÖYÜ*\n"
    msg += f"💰 *Toplam Varlık:* `{equity:.2f}$`\n"
    msg += f"💵 *Nakit:* `{available:.2f}$`\n"
    msg += f"{pnl_color} *Toplam K/Z:* `{total_pnl:+.2f}$`\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    
    if pos_details: 
        msg += pos_details + "\n"
    else: 
        if idle_reason:
            msg += f"   _Nakitteyiz, Sebepler:_\n{idle_reason}\n"
        else:
            msg += "   _Nakitteyiz, fırsat kolluyoruz._\n\n"
    
    return msg, equity

def manage_trade(symbol, signal, price, atr=0, reasons=[]):
    """İşlem açar/kapatır ve Trailing Stop/Partial TP yönetir"""
    if symbol not in COINS: 
        return None
        
    wallet = safe_load_wallet()
    if not wallet: return None
    log = ""
    close_condition = False
    stop_hit = False
    reason = ""
    
    # Mevcut pozisyon varsa yönet
    if symbol in wallet['positions']:
        pos = wallet['positions'][symbol]
        
        # PNL Hesapla
        pnl_now = ((price - pos['entry']) / pos['entry']) if pos['type'] == 'LONG' else ((pos['entry'] - price) / pos['entry'])

        # 1. Kademeli Kar Alım (Partial TP)
        if 'partial_tp_hit' not in pos:
            if pnl_now >= 0.03: 
                profit_usd = (pos['amount'] * 0.5) * (pnl_now * LEVERAGE)
                wallet['available_balance'] += (pos['amount'] * 0.5) + profit_usd
                wallet['total_profit'] += profit_usd
                pos['amount'] *= 0.5 
                pos['partial_tp_hit'] = True
                pos['stop_loss'] = pos['entry']
                log += f"🎯 *KISMİ KAR ALINDI (%50):* `{symbol}` | PNL: `{profit_usd:+.2f}$`\n"

        # 2. İzleyen Stop (Trailing Stop)
        if pnl_now >= 0.05:
            new_sl = price * 0.98 if pos['type'] == 'LONG' else price * 1.02
            if pos['type'] == 'LONG':
                if new_sl > pos['stop_loss']: pos['stop_loss'] = new_sl
            else:
                if new_sl < pos['stop_loss']: pos['stop_loss'] = new_sl

        # 3. Kâr Alma (Take Profit %20+)
        if pnl_now >= 0.20:
             close_condition = True
             reason = "💰 KAR ALINDI (%20+)"

        # 4. Kapatma Koşulları
        if not close_condition:
            close_condition = (pos['type'] == 'LONG' and signal == 'SAT') or \
                              (pos['type'] == 'SHORT' and signal == 'AL')
        
        sl_level = pos.get('stop_loss', 0)
        if sl_level > 0:
            if (pos['type'] == 'LONG' and price < sl_level) or \
               (pos['type'] == 'SHORT' and price > sl_level):
                stop_hit = True

        if close_condition or stop_hit:
            pnl_pct = ((price - pos['entry']) / pos['entry']) * LEVERAGE if pos['type'] == 'LONG' else ((pos['entry'] - price) / pos['entry']) * LEVERAGE
            profit = pos['amount'] * pnl_pct
            wallet['available_balance'] += pos['amount'] + profit
            wallet['total_profit'] += profit
            
            if stop_hit: 
                reason = "🛑 STOP OLDU"
            elif not reason: 
                reason = "💰 KAPAT"
                
            del wallet['positions'][symbol]
            log += f"[{reason}]: `{symbol}` Finansal: `{profit:+.2f}$` (%{pnl_pct*100:.2f})"
            
            # PNL Kartı Oluştur ve Gönder
            try:
                card_path = generate_pnl_card(
                    symbol, pos['type'], pos['entry'], price, 
                    profit, pnl_pct, LEVERAGE
                )
                if card_path:
                    caption = f"{reason} - {symbol}\n💰 PNL: `{profit:+.2f}$`"
                    send_telegram_photo(card_path, caption)
                    try: os.remove(card_path)
                    except: pass
            except Exception as e:
                print(f"Kart hatası: {e}")
    
    # Yeni pozisyon aç
    elif signal in ['AL', 'SAT']:
        hour = datetime.now().hour
        if 0 <= hour <= 4:
            return f"⏳ `{symbol}` Pasif Saatler (00-04). İşlem Açılmadı."
            
        margin = wallet['available_balance'] * 0.25 
        if margin > 10: 
            wallet['available_balance'] -= margin
            # ATR fallback (if ATR is 0, use 2% of price)
            safe_atr = atr if atr > 0 else (price * 0.01)
            sl = price - (2 * safe_atr) if signal == "AL" else price + (2 * safe_atr)
            
            wallet['positions'][symbol] = {
                "type": "LONG" if signal == "AL" else "SHORT",
                "entry": price, 
                "amount": margin, 
                "stop_loss": sl,
                "source": "Otomatik",
                "time": datetime.now().strftime('%H:%M:%S')
            }
            log = f"🎰 *GİRİŞ:* `{symbol}` {signal} (x{LEVERAGE})\n"
            log += f"🛡️ İlk Stop: `{sl:.2f}$` | Giriş: `{price:.2f}$`\n"
            if reasons:
                log += f"🧠 *STRATEJİK GEREKÇELER:*\n"
                for r in reasons:
                    log += f"   ➤ {r}\n"
        
    # Geçmişe kaydet
    equity = wallet['available_balance'] + sum([p['amount'] for p in wallet['positions'].values()])
    if "equity_history" not in wallet: wallet["equity_history"] = []
    wallet['equity_history'].append({"time": time.time(), "equity": equity})
    wallet['equity_history'] = wallet['equity_history'][-100:]

    safe_save_wallet(wallet)
    return log

# ================== VERİ TOPLAMA ==================
def get_market_sentiment():
    """Piyasa psikolojisi ve BTC dominansını getirir"""
    try:
        # Fear & Greed Index
        data_fng = robust_json_get("https://api.alternative.me/fng/?limit=31")
        if not data_fng or 'data' not in data_fng: 
            return "⚠️ Psikoloji Verisi Alınamadı"
        fng = data_fng['data']
            
        n = int(fng[0]['value'])
        y = int(fng[1]['value']) if len(fng) > 1 else 0
        w = int(fng[7]['value']) if len(fng) > 7 else 0
        m = int(fng[30]['value']) if len(fng) > 30 else 0
        ic = "↗️" if n > y else "↘️"
        
        msg = f"🧠 *PSİKOLOJİ:* {n} ({fng[0]['value_classification']}) {ic}\n"
        msg += f"▪️ `Dün  ` {y}\n▪️ `Hafta` {w}\n▪️ `Ay   ` {m}\n\n"
        
        # BTC Dominans
        d = robust_json_get("https://api.coingecko.com/api/v3/global")
        if not d or 'data' not in d: return msg + "📊 *BTC DOMINANS:* `⚠️ Veri Hatası`"
        btc_d = float(d['data']['market_cap_percentage']['btc'])
        msg += f"📊 *BTC DOMINANS:* `%{btc_d:.2f}`\n"
        
        # Dominans Trendleri
        base = "https://fapi.binance.com"
        for tf in TIMEFRAMES:
            k = robust_json_get(
                f"{base}/fapi/v1/klines", 
                params={'symbol': 'BTCDOMUSDT', 'interval': tf, 'limit': 50}
            )
            
            if k:
                c = float(k[-1][4])  # Close
                o = float(k[-1][1])  # Open
                pct = ((c - o) / o) * 100
                icon = "📈" if pct > 0 else "📉"
                
                tf_label = tf.replace("15m","15D").replace("1h","1S") \
                             .replace("4h","4S").replace("1d","1G").replace("1M","1Ay")
                msg += f"▪️ `{tf_label:<3}` {icon} `%{pct:+.2f}`\n"
                
        return msg
    except Exception as e: 
        print(f"Sentiment hatası: {e}")
        return "⚠️ Veri Hatası"

def get_pivot_levels(symbol):
    """Pivot Destek/Direnç seviyeleri (S1/R1)"""
    try:
        k = robust_json_get(
            "https://fapi.binance.com/fapi/v1/klines", 
            params={'symbol': symbol, 'interval': '1d', 'limit': 2}
        )
        if not k or not isinstance(k, list) or len(k) < 1: return 0, 0
        
        h = float(k[0][2])  # High
        l = float(k[0][3])  # Low
        c = float(k[0][4])  # Close
        
        pivot = (h + l + c) / 3
        s1 = (2 * pivot) - h  # Destek
        r1 = (2 * pivot) - l  # Direnç
        
        return s1, r1
    except: 
        return 0, 0

def get_funding_rates(symbols):
    """Fonlama oranlarını getirir (Long/Short baskısı)"""
    rates = {}
    try:
        data = robust_json_get(
            "https://fapi.binance.com/fapi/v1/premiumIndex", 
            timeout=5
        )
        if not data: return {}
        
        for item in data:
            if item['symbol'] in symbols:
                rates[item['symbol']] = float(item['lastFundingRate'])
    except Exception as e:
        print(f"Funding rate hatası: {e}")
        
    return rates

def get_news_sentiment():
    """Haber arşivini tarar ve piyasa korkusunu ölçer"""
    try:
        fpath = get_data_path("news_archive.json")
        if not os.path.exists(fpath): return "Nötr"
        with open(fpath, 'r', encoding='utf-8') as f:
            news = json.load(f)
        
        fear_keywords = ["crash", "dump", "bear", "hack", "scam", "down", "sec", "lawsuit"]
        bull_keywords = ["moon", "pump", "bull", "buy", "growth", "adoption", "etf", "high"]
        
        score = 0
        latest = news[:20] # Son 20 haber
        for n in latest:
            txt = n.get('title', '').lower()
            for k in fear_keywords:
                if k in txt: score -= 1
            for k in bull_keywords:
                if k in txt: score += 1
        
        if score <= -3: return "⚠️ PANİK / AYI"
        if score >= 3: return "🚀 COŞKU / BOĞA"
        return "⚖️ Nötr / Stabil"
    except: return "Bilinmiyor"

# ================== TEKNİK İNDİKATÖRLER ==================
def check_fvg(df):
    """Fair Value Gap - Fiyat boşluğu tespiti"""
    if len(df) < 3: 
        return ""
    
    # Boğa FVG: 3 mum önceki high < şimdiki low
    m1_h = df['h'].iloc[-3]
    m3_l = df['l'].iloc[-1]
    if m3_l > m1_h: 
        return "🟢 FVG"
    
    # Ayı FVG: 3 mum önceki low > şimdiki high
    m1_l = df['l'].iloc[-3]
    m3_h = df['h'].iloc[-1]
    if m3_h < m1_l: 
        return "🔴 FVG"
    
    return ""

def check_divergence(df):
    """RSI Divergence - Fiyat/Momentum uyumsuzluğu"""
    if len(df) < 15: 
        return ""
    
    price = df['c']
    rsi = df['rsi']
    
    # Pozitif Divergence: Fiyat düşüyor ama RSI yükseliyor
    if price.iloc[-1] < price.iloc[-5] and rsi.iloc[-1] > rsi.iloc[-5]: 
        return "✅ PU (Dönüş)"
    
    # Negatif Divergence: Fiyat yükseliyor ama RSI düşüyor
    if price.iloc[-1] > price.iloc[-5] and rsi.iloc[-1] < rsi.iloc[-5]: 
        return "⚠️ NU (Düşüş)"
    
    return ""

def check_candles(df):
    """Mum formasyonu analizi"""
    if len(df) < 2:
        return ""
        
    row = df.iloc[-1]
    prev = df.iloc[-2]
    body = abs(row['c'] - row['o'])
    total_range = row['h'] - row['l']
    
    # Doji - Kararsızlık
    if body < total_range * 0.1: 
        return "🕯️ Doji"
    
    # Çekiç - Dip sinyali
    lower_wick = min(row['c'], row['o']) - row['l']
    if lower_wick > body * 2: 
        return "🔨 Çekiç"
    
    # Yutan Boğa - Güçlü yükseliş
    if row['c'] > row['o'] and prev['c'] < prev['o'] and row['c'] > prev['o']: 
        return "🔥 YutanB"
    
    return ""

# ================== ANA ANALİZ MOTORU ==================
def analyze_tf(symbol, tf):
    """Teknik analiz yapar (RSI, ATR, ADX dahil)"""
    try:
        limit = 200 if tf != "1M" else 50
        k = robust_json_get(
            "https://fapi.binance.com/fapi/v1/klines", 
            params={'symbol': symbol, 'interval': tf, 'limit': limit}
        )
        if not k or len(k) < 30: return None
        
        df = pd.DataFrame(k, columns=['t','o','h','l','c','v','x','q','n','tb','tq','i']).astype(float)
        cur, prev = df['c'].iloc[-1], df['c'].iloc[-2]
        
        # 1. RSI
        delta = df['c'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        df['rsi'] = 100 - (100 / (1 + gain / loss))
        
        # 2. ATR
        df['tr'] = pd.concat([df['h']-df['l'], abs(df['h']-df['c'].shift()), abs(df['l']-df['c'].shift())], axis=1).max(axis=1)
        df['atr'] = df['tr'].rolling(14).mean()
        
        # 3. ADX (Trend Gücü)
        df['up'] = df['h'].diff(); df['dn'] = -df['l'].diff()
        df['+dm'] = np.where((df['up']>df['dn']) & (df['up']>0), df['up'], 0)
        df['-dm'] = np.where((df['dn']>df['up']) & (df['dn']>0), df['dn'], 0)
        df['+di'] = 100 * (df['+dm'].rolling(14).mean() / df['atr'])
        df['-di'] = 100 * (df['-dm'].rolling(14).mean() / df['atr'])
        df['dx'] = 100 * abs(df['+di'] - df['-di']) / (df['+di'] + df['-di'])
        df['adx'] = df['dx'].rolling(14).mean()
        
        ema50 = df['c'].ewm(span=50).mean().iloc[-1]
        ema65 = df['c'].ewm(span=65).mean().iloc[-1]
        
        return {
            "rsi": df['rsi'].iloc[-1], 
            "adx": df['adx'].iloc[-1],
            "trend": "📈" if cur > ema50 else "📉", 
            "c": cur, "prev": prev,
            "ema50": ema50,
            "ema65": ema65,
            "sq": (df['c'].rolling(20).std() * 4 / df['c'].rolling(20).mean()).iloc[-1] < 0.01,
            "wh": df['v'].iloc[-1] > (df['v'].rolling(20).mean().iloc[-1] * 2.5),
            "fvg": check_fvg(df), "div": check_divergence(df), "candle": check_candles(df),
            "atr": df['atr'].iloc[-1]
        }
    except Exception as e:
        print(f"Hata {symbol} {tf}: {e}")
        return None
    except Exception as e:
        print(f"Analiz hatası ({symbol} {tf}): {e}")
        return None

# ================== STRATEJİ & KARAR MEKANİZMASI ==================
def generate_strategy(rsi15, rsi4h, price, s1, r1, trend4h, candle, atr, div, fvg, is_squeeze, adx=0, btc_trend="", ema50=0, ema65=0):
    """
    Gelişmiş Strateji Motoru - Mantıksal detayları ve sinyali üretir
    """
    signal = "NÖTR"
    desc = "Piyasa şu an dinleniyor."
    stop_level = 0
    confidence = 65 
    reasons = [] # Giriş gerekçeleri
    
    # Mantıksal teşhis tablosu
    logic_diagnostics = {
        "adx_val": adx,
        "adx_status": "GÜÇLÜ TREND" if adx > 25 else ("ZAYIF TREND" if adx > 20 else "YATAY PİYASA"),
        "btc_corr": "UYUMLU ✅" if btc_trend == trend4h else "ZIT ⚠️",
        "time_filter": "AKTİF ✅" if not (0 <= datetime.now().hour <= 4) else "PASİF ⏳",
        "volatility": "NORMAL" if atr/price < 0.05 else "YÜKSEK 🔥",
    }

    # 1. ADX Filtresi
    if adx < 22:
        return "NÖTR", f"📉 TEST: Piyasa Yatay (ADX:{adx:.1f}). İşlem için trend bekle.", 0, logic_diagnostics, []

    # 2. BTC Korelasyonu
    if btc_trend and btc_trend != trend4h:
        confidence -= 20
        
    # 3. Güven Puanı İnce Ayar
    if trend4h == "📈": 
        confidence += 10
        reasons.append(f"EMA 50 Üzerinde (Trend Pozitif)")
    
    if ema65 > 0:
        if price > ema65: reasons.append(f"EMA 65 Üzerinde (Long Uygun)")
        else: reasons.append(f"EMA 65 Altında (Short Uygun)")

    if "Çekiç" in str(candle) or "YutanB" in str(candle): 
        confidence += 15
        reasons.append(f"Güçlü Mum Formasyonu: {candle}")
        
    if "PU" in str(div): 
        confidence += 10
        reasons.append(f"RSI Pozitif Uyumsuzluk (Dönüş)")
        
    if is_squeeze: confidence -= 10
    
    confidence = max(40, min(95, confidence))
    margin = 0.005 

    # Sinyaller ve Ek Gerekçeler
    if price > r1 * (1 + margin) and trend4h == "📈" and confidence > 70:
        signal = "AL"
        desc = f"🌊 *BREAKOUT LONG:* R1 Kırıldı. (Güven: %{confidence})"
        reasons.append(f"R1 Direnci Kırıldı ({r1:.0f}$)")
        stop_level = price - (1.5 * atr)
    
    elif price < s1 * (1 - margin) and trend4h == "📉" and confidence > 70:
        signal = "SAT"
        desc = f"🚨 *BREAKOUT SHORT:* S1 Kırıldı. (Güven: %{confidence})"
        reasons.append(f"S1 Desteği Kırıldı ({s1:.0f}$)")
        stop_level = price + (1.5 * atr)
    
    elif rsi15 < 30 and price <= s1 * 1.01 and trend4h == "📈":
        signal = "AL"
        desc = f"🟢 *DİP ALIMI:* Destek + Aşırı Satım. (Güven: %{confidence})"
        reasons.append(f"RSI Aşırı Satım ({rsi15:.0f}) + Destek Teması")
        stop_level = price - (2 * atr)

    return signal, desc, stop_level, logic_diagnostics, reasons
# ================== GÖRSEL DASHBOARD ==================
def generate_dashboard_image():
    """Heatmap ve Bollinger grafiği oluşturur"""
    try:
        base = "https://fapi.binance.com"
        
        # Anlık fiyat
        pi = robust_json_get(
            f"{base}/fapi/v1/ticker/price", 
            params={'symbol': 'BTCUSDT'}
        )
        if not pi: return None, None
        curr = float(pi['price'])
        
        # 4H kline verisi
        klines = robust_json_get(
            f"{base}/fapi/v1/klines", 
            params={'symbol': 'BTCUSDT', 'interval': '4h', 'limit': 500}
        )
        if not klines: return None, None
        
        df = pd.DataFrame(
            klines, 
            columns=['t','o','h','l','c','v','x','q','n','tb','tq','i']
        ).astype(float)
        
        plt.style.use('dark_background')
        fig, (ax1, ax2) = plt.subplots(
            2, 1, 
            figsize=(10, 12), 
            gridspec_kw={'height_ratios': [1, 1]}
        )
        
        # 1. LİKİDİTE HEATMAP
        df_map = df[
            (df['c'] >= curr - 15000) & 
            (df['c'] <= curr + 15000)
        ]
        hist, bins = np.histogram(
            df_map['c'], 
            bins=np.arange(curr - 15000, curr + 15000, 300), 
            weights=df_map['v']
        )
        
        ax1.barh(
            0.5 * (bins[:-1] + bins[1:]), 
            hist, 
            height=250, 
            color=plt.cm.viridis(plt.Normalize(hist.min(), hist.max())(hist)), 
            alpha=0.85
        )
        ax1.axhline(curr, color='red', linestyle='-', linewidth=1.5, label='ŞU AN')
        ax1.set_title('LİKİDİTE DUVARLARI (HEATMAP)', color='white', fontsize=10)
        ax1.legend()
        
        # 2. BOLLINGER BANDS
        df_bb = df.tail(100).copy()
        df_bb['sma'] = df_bb['c'].rolling(20).mean()
        df_bb['std'] = df_bb['c'].rolling(20).std()
        df_bb['u'] = df_bb['sma'] + (2 * df_bb['std'])
        df_bb['l'] = df_bb['sma'] - (2 * df_bb['std'])
        
        ax2.plot(range(len(df_bb)), df_bb['c'], color='white', linewidth=1.5, label='Fiyat')
        ax2.plot(range(len(df_bb)), df_bb['u'], color='cyan', linestyle='--', alpha=0.5)
        ax2.plot(range(len(df_bb)), df_bb['l'], color='cyan', linestyle='--', alpha=0.5)
        ax2.fill_between(
            range(len(df_bb)), 
            df_bb['u'], 
            df_bb['l'], 
            color='cyan', 
            alpha=0.1
        )
        ax2.set_title('TREND VE SIKIŞMA (BOLLINGER)', color='white', fontsize=10)
        ax2.set_xticks([])
        
        fn = "dashboard_v30.png"
        plt.tight_layout()
        plt.savefig(fn, dpi=100)
        plt.close()
        
        return fn, "🖼️ *GÖRSEL ANALİZ*"
    except Exception as e:
        print(f"Görsel oluşturma hatası: {e}")
        return None, None

# ================== AÇIKLAMA FONKSİYONLARI ==================
def explain_candle(candle_type):
    """Mum formasyonu açıklaması"""
    explanations = {
        "🕯️ Doji": "Alıcı/satıcı dengesizdir, kararsızlık var. Trend dönüşü gelebilir.",
        "🔨 Çekiç": "Dip sinyali! Satıcılar bastırdı ama alıcılar geri itti. Yükseliş olabilir.",
        "🔥 YutanB": "Güçlü yükseliş! Önceki ayı mumunu tamamen yutan boğa mumu. Momentum bizde."
    }
    return explanations.get(candle_type, "")

def explain_s1_risk(price, s1):
    """S1 seviyesi ve şelale riski açıklaması"""
    distance_pct = ((price - s1) / s1) * 100
    
    if price < s1:
        return f"⚠️ *DESTEK KIRILDI!* Fiyat S1'in altında (%{abs(distance_pct):.2f} aşağıda). Şelale riski yüksek - hızlı düşüş gelebilir!"
    elif price <= s1 * 1.02:
        return f"🟡 *DESTEK YAKININDA:* S1'e çok yakınız (%{distance_pct:.2f} üstünde). Kırılırsa şelale başlayabilir."
    else:
        return f"✅ *GÜVENLİ BÖLGE:* S1'den %{distance_pct:.2f} uzaktayız. Destek sağlam."

def explain_confidence(confidence):
    """Güven puanı açıklaması"""
    if confidence >= 85:
        return "🔥 ÇOK GÜÇLÜ - Tüm sinyaller uyumlu, yüksek başarı olasılığı."
    elif confidence >= 75:
        return "💪 GÜÇLÜ - Çoğu faktör lehimizde, iyi giriş noktası."
    elif confidence >= 65:
        return "✅ ORTA - Makul seviye, ancak dikkatli olalım."
    elif confidence >= 55:
        return "⚠️ ZAYIF - Az sayıda destekleyici sinyal, riskli."
    else:
        return "🚫 ÇOK ZAYIF - Sinyaller çelişkili, beklemek daha iyi."

# ================== ANA RAPOR ==================
def generate_full_report(live_trade=False):
    """Tüm analizleri birleştirip tek mesaj oluşturur"""
    
    # Fiyatları çek
    curr_prices = {}
    symbols = COINS.copy()
    
    for c in COINS:
        try: 
            p_data = robust_json_get(
                f"https://fapi.binance.com/fapi/v1/ticker/price", 
                params={'symbol': c}
            )
            curr_prices[c] = float(p_data['price']) if p_data and 'price' in p_data else 0
        except: 
            curr_prices[c] = 0
    
    # Fonlama oranları
    funding_rates = get_funding_rates(symbols)
    
    # Sentiment
    sentiment = get_market_sentiment()
    news_sent = get_news_sentiment()
    
    # BTC Trendini Al (Korelasyon için bir kez)
    btc_d4h = analyze_tf("BTCUSDT", "4h")
    btc_trend_val = btc_d4h['trend'] if btc_d4h else "Bilinmiyor"

    # STRATEJİ TOPLAMA (Nakit durumu açıklaması için)
    coin_analyses = {}
    idle_reasons = []

    for coin in COINS:
        s1, r1 = get_pivot_levels(coin)
        d15 = analyze_tf(coin, "15m")
        d1h = analyze_tf(coin, "1h")
        d4h = analyze_tf(coin, "4h")
        
        if d15 and d4h:
            candle_info = d1h['candle'] if d1h else ""
            sig, desc, stop, diag, reasons = generate_strategy(
                d15['rsi'], d4h['rsi'], d15['c'], s1, r1, 
                d4h['trend'], candle_info, d15['atr'], 
                d15['div'], d15['fvg'], d15['sq'],
                adx=d15.get('adx', 0), btc_trend=btc_trend_val,
                ema50=d15.get('ema50', 0), ema65=d15.get('ema65', 0)
            )
            coin_analyses[coin] = {
                's1': s1, 'r1': r1, 'd15': d15, 'd1h': d1h, 'd4h': d4h,
                'sig': sig, 'desc': desc, 'stop': stop, 'diag': diag, 'reasons': reasons
            }
            if sig == "NÖTR":
                # Sadece ana engelleri ekle (ADX, BTC zıtlık vb)
                if diag['adx_val'] < 22:
                    idle_reasons.append(f"   ➤ {coin}: Yatay Piyasa (ADX:{diag['adx_val']:.1f})")
                elif btc_trend_val != d4h['trend']:
                    idle_reasons.append(f"   ➤ {coin}: BTC Trendiyle Uyumsuz")
                else:
                    idle_reasons.append(f"   ➤ {coin}: Güçlü Sinyal Yok (Güven Düşük)")

    # Cüzdan Raporu (Analizlerden gelen veriye göre)
    unique_idle = list(set(idle_reasons))[:3] # Çok kalabalık olmasın
    wallet_msg, equity = get_wallet_status(curr_prices, idle_reason="\n".join(unique_idle) if unique_idle else "")
    
    # ═══════════════════════════════════════
    # MESAJ BAŞLANGIÇ
    # ═══════════════════════════════════════
    msg = f"👑 *ÜLGEN v30 - ULTIMUS MAXIMUS* 👑\n\n"
    msg += "v27 den *MEVCUT ÖZELLİKLER:*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "• 🎯 *YÖN BELİRLEME:* Long/Short açıkça gösteriliyor\n"
    msg += "• 📊 *GÜVEN PUANI:* Her sinyalin güvenilirlik skoru\n"
    msg += "• 🕯️ *MUM ANALİZİ:* Formasyonlar detaylı açıklanıyor\n"
    msg += "• 🧱 *S1 ŞELALE RİSKİ:* Destek kırılımı uyarısı\n"
    msg += "• 💰 *FUNDING RATE:* Long/Short baskısı gösteriliyor\n"
    msg += "• 📚 *TERİMLER:* Her mesajda kısa açıklamalar\n\n"
    
    msg += "✅ *V30 YENİ ÖZELLİKLER:*\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    msg += "• 🛰️ *ADX FİLTRESİ:* Yatay piyasada işlem açmaz.\n"
    msg += "• 🎯 *PARSİYEL KAR:* %3 karda %50 nakite geçer.\n"
    msg += "• 🛡️ *İZLEYEN STOP:* Kârı koruyan takip sistemi.\n"
    msg += "• 📰 *HABER DUYGUSU:* Yapay zeka haber taraması.\n"
    msg += "• ⛓️ *BTC KORELASYON:* Ana trend onayı şartı.\n"
    msg += "• ⏳ *ZAMAN FİLTRESİ:* Düşük likidite koruması.\n"
    msg += "━━━━━━━━━━━━━━━━━━\n\n"
    msg += sentiment + "\n"
    msg += wallet_msg
    msg += "━━━━━━━━━━━━━━━━━━\n\n"
    
    # ═══════════════════════════════════════
    # HER COİN İÇİN ANALİZ
    # ═══════════════════════════════════════
    for coin in COINS:
        analysis = coin_analyses.get(coin)
        if not analysis: continue

        s1, r1 = analysis['s1'], analysis['r1']
        d15, d4h = analysis['d15'], analysis['d4h']
        price = d15['c']
        
        # Funding Rate
        fund_rate = funding_rates.get(coin, 0)
        fund_color = "🟢" if fund_rate > 0 else "🔴" if fund_rate < 0 else "⚪"
        
        msg += f"🪙 *{coin}*: `{price:.2f}$`\n"
        msg += f"   {fund_color} Funding: `%{fund_rate:.4f}` "
        msg += f"({'Long baskısı' if fund_rate > 0 else 'Short baskısı' if fund_rate < 0 else 'Nötr'})\n"
        
        # Tüm timeframe'ler
        for tf in TIMEFRAMES:
            d = analyze_tf(coin, tf)
            if d:
                # İkonlar
                icons = ""
                if d['rsi'] < 30: icons += "🚨"
                elif d['rsi'] > 70: icons += "⚠️"
                if d['sq']: icons += "💥"
                if d['wh']: icons += "🐋"
                if d['div']: icons += "🔄"
                if d['fvg']: icons += "🧲"
                
                tf_label = tf.replace("15m","15D").replace("1h","1S") \
                             .replace("4h","4S").replace("1d","1G").replace("1M","1Ay")
                
                pr = d['c'] if tf == "15m" else d['prev']
                msg += f"▪️ `{tf_label:<3}` {d['trend']} | RSI:{d['rsi']:.0f} {icons} | `{pr:.2f}$`\n"
                
                # Detaylar
                details = []
                if d['candle'] and tf in ["15m", "1h", "4h"]: 
                    details.append(d['candle'])
                if d['div']: 
                    details.append(d['div'])
                if d['fvg'] and tf in ["15m", "1h"]: 
                    details.append(d['fvg'])
                
                if details: 
                    msg += f"   ↳ _{' | '.join(details)}_\n"
        
        # Pivot seviyeleri
        msg += f"\n🧱 *Destek (S1):* `{s1:.0f}$` | *Direnç (R1):* `{r1:.0f}$`\n"
        
        # ═══════════════════════════════════════
        # STRATEJİ VE AÇIKLAMALAR
        # ═══════════════════════════════════════
        sig, desc, stop, diag, reasons = analysis['sig'], analysis['desc'], analysis['stop'], analysis['diag'], analysis['reasons']
        candle_info = analysis['d1h']['candle'] if analysis['d1h'] else ""

        # 🧩 STRATEJİK MANTIK DIŞAVURUMU
        msg += f"🧠 *STRATEJİK MANTIK ANALİZİ:*\n"
        msg += f"   ├ 🛰️ ADX: `{diag['adx_val']:.1f}` ({diag['adx_status']})\n"
        msg += f"   ├ ⛓️ BTC Korel: `{diag['btc_corr']}`\n"
        msg += f"   ├ 📰 Haber Duygusu: `{news_sent}`\n"
        msg += f"   ├ ⏳ Seans Durumu: `{diag['time_filter']}`\n"
        msg += f"   └ 📈 Volatilite: `{diag['volatility']}`\n"
        
        # Güven puanını çıkar
        conf_match = re.search(r'%(\d+)', desc)
        confidence = int(conf_match.group(1)) if conf_match else 60
        
        # ── YÖN BELİRLE ──
        if sig == "AL":
            direction = "🟢 *YÖN: LONG* 📈"
        elif sig == "SAT":
            direction = "🔴 *YÖN: SHORT* 📉"
        else:
            direction = "⚪ *YÖN: NÖTR* ⏸️"
        
        msg += f"\n{direction}\n"
        msg += f"💡 {desc}\n"
        
        # ── GÜVEN PUANI AÇIKLAMASI ──
        conf_explain = explain_confidence(confidence)
        msg += f"📊 *Güven Açıklaması:* {conf_explain}\n"
        
        # ── MUM FORMASYONU AÇIKLAMASI ──
        if candle_info:
            candle_explain = explain_candle(candle_info)
            if candle_explain:
                msg += f"🕯️ *Mum Analizi:* {candle_explain}\n"
        
        # ── S1 RİSK AÇIKLAMASI ──
        s1_explain = explain_s1_risk(price, s1)
        msg += f"{s1_explain}\n"
        
        # ── STOP LOSS ──
        if sig != "NÖTR":
            msg += f"🛡️ *İlk Stop (ATR):* `{stop:.2f}$`\n"
            
            # BTC, ETH ve TAO için işlem yönetimi
            if live_trade:
                log = manage_trade(coin, sig, price, d15['atr'], reasons=reasons)
                if log: 
                    msg += f"\n{log}\n"
            else:
                msg += f"ℹ️ _Test Modu: İşlem açılmadı._\n"
        
        msg += "━━━━━━━━━━━━━━━━━━\n"
    
    # ═══════════════════════════════════════
    # FOOTER AÇIKLAMALAR
    # ═══════════════════════════════════════
    msg += f"\n📚 *TERİMLER KISA AÇIKLAMA:*\n"
    msg += f"• *Güven Puanı:* Sinyalin güvenilirliği (50-95). Trend, mum formasyonu, divergence gibi faktörlerden hesaplanır.\n"
    msg += f"• *S1 (Destek):* Fiyatın tutunması beklenen seviye. Kırılırsa 'şelale' başlar (hızlı düşüş).\n"
    msg += f"• *R1 (Direnç):* Fiyatın zorlanacağı tavan. Kırılırsa yeni yükseliş dalgası.\n"
    msg += f"• *FVG:* Likidite boşluğu, fiyat bu bölgeyi doldurmaya çalışır.\n"
    msg += f"• *Divergence:* RSI ile fiyat ters yönde → Trend dönüşü gelebilir.\n"
    msg += f"• *Funding Rate:* Pozitif = Long baskısı (çok long var), Negatif = Short baskısı.\n\n"
    
    msg += f"🕒 {datetime.now().strftime('%H:%M')} | _Ülgen Han_"
    
    return msg

# ================== ANA PROGRAM DÖNGÜSÜ ==================
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 ÜLGEN v30.0 - İMPARATORUN KILICI AKTİF")
    print("=" * 60)
    print(f"📅 Başlangıç Zamanı: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 Başlangıç Bakiyesi: {INITIAL_BALANCE}$")
    print(f"⚡ Kaldıraç: x{LEVERAGE}")
    print(f"🎯 Hedef Coin: {TARGET_COIN}")
    print(f"📊 İzlenen Coinler: {', '.join(COINS)}")
    print(f"⏱️ Timeframe'ler: {', '.join(TIMEFRAMES)}")
    print(f"📱 Telegram: {CHAT_ID}")
    print("=" * 60)
    
    # İlk başlangıç mesajı
    startup_msg = """
📢 *ÜLGEN v30.0 - ULTIMUS MAXIMUS AKTIF!* 

v27 den *MEVCUT ÖZELLİKLER:*
━━━━━━━━━━━━━━━━━━━━━━
• 🎯 *YÖN BELİRLEME:* Long/Short açıkça gösteriliyor
• 📊 *GÜVEN PUANI:* Her sinyalin güvenilirlik skoru
• 🕯️ *MUM ANALİZİ:* Formasyonlar detaylı açıklanıyor
• 🧱 *S1 ŞELALE RİSKİ:* Destek kırılımı uyarısı
• 💰 *FUNDING RATE:* Long/Short baskısı gösteriliyor
• 📚 *TERİMLER:* Her mesajda kısa açıklamalar

✅ *V30 YENİ ÖZELLİKLER:*
━━━━━━━━━━━━━━━━━━
• 🛰️ *ADX FİLTRESİ:* Yatay piyasada işlem açmaz.
• 🎯 *PARSİYEL KAR:* %3 karda %50 nakite geçer.
• 🛡️ *İZLEYEN STOP:* Kârı koruyan takip sistemi.
• 📰 *HABER DUYGUSU:* Yapay zeka haber taraması.
• ⛓️ *BTC KORELASYON:* Ana trend onayı şartı.
• ⏳ *ZAMAN FİLTRESİ:* Düşük likidite koruması.

━━━━━━━━━━━━━━━━━━━━━━
🔥 *TEK MESAJDA KOMPLE ANALİZ!*
Her 15 dakikada bir tam rapor geliyor.

İmparator hazır, piyasalar bizim! 👑
    """
    
    send_telegram_message(startup_msg)
    print("\n✅ Telegram'a başlangıç mesajı gönderildi!")
    print("\n🔄 Ana döngü başlıyor...\n")
    
    # Döngü sayacı
    cycle_count = 0
    last_report_time = 0
    REPORT_INTERVAL = 900  # 15 dakika
    CHECK_INTERVAL = 10    # 10 saniye

    print(f"\n✅ Hızlı Takip Modu Aktif (Kontrol: {CHECK_INTERVAL}sn | Rapor: {REPORT_INTERVAL}sn)\n")

    while True:
        try:
            current_timestamp = time.time()
            current_time_str = datetime.now().strftime('%H:%M:%S')

            # ═══════════════════════════════════════
            # 1. SL/TP VE POZİSYON KONTROLÜ (HIZLI)
            # ═══════════════════════════════════════
            # Her döngüde anlık fiyatları çekip stop/kar kontrolü yapalım
            for coin in COINS:
                try:
                    # Hızlı fiyat kontrolü
                    p_data = robust_json_get(
                        f"https://fapi.binance.com/fapi/v1/ticker/price", 
                        params={'symbol': coin},
                        timeout=3
                    )
                    if p_data and 'price' in p_data:
                        price = float(p_data['price'])
                        # Sinyal "NÖTR" gönderiyoruz ki yeni işlem açmasın, sadece yönetin
                        log = manage_trade(coin, "NÖTR", price)
                        if log:
                            print(f"\n⚡ İŞLEM GÜNCELLEME: {log}")
                            send_telegram_message(log)
                except Exception as e:
                    print(f"⚠️ Fiyat kontrol hatası ({coin}): {e}")

            # ═══════════════════════════════════════
            # 2. RAPORLAMA ZAMANI GELDİ Mİ?
            # ═══════════════════════════════════════
            if current_timestamp - last_report_time >= REPORT_INTERVAL:
                cycle_count += 1
                last_report_time = current_timestamp
                
                print(f"\n{'=' * 60}")
                print(f"🔄 ANALİZ DÖNGÜSÜ #{cycle_count} | {current_time_str}")
                print(f"{'=' * 60}")
                
                # A. GÖRSEL ANALİZ GÖNDER
                print("📊 Görsel dashboard oluşturuluyor...")
                img, cap = generate_dashboard_image()
                
                if img and cap:
                    print(f"   ✅ Görsel oluşturuldu: {img}")
                    send_telegram_photo(img, cap)
                    print(f"   📤 Telegram'a gönderildi!")
                else:
                    print(f"   ⚠️ Görsel oluşturulamadı (atlanıyor)")
                
                # B. TAM RAPOR GÖNDER
                print("\n📝 Tam rapor oluşturuluyor...")
                report = generate_full_report(live_trade=True)
                
                print(f"   ✅ Rapor hazır ({len(report)} karakter)")
                send_telegram_message(report)
                print(f"   📤 Telegram'a gönderildi!")

            # Bekleme (Hızlı döngü için kısa süre)
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n\n" + "=" * 60)
            print("⛔ KULLANICI TARAFINDAN DURDURULDU (Ctrl+C)")
            print("=" * 60)
            
            shutdown_msg = f"""
🛑 *ÜLGEN v30.0 DURDURULDU*

📊 *ÖZET:*
• Toplam Döngü: {cycle_count}
• Durdurma Zamanı: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Tekrar görüşmek üzere İmparator! 👑
            """
            
            send_telegram_message(shutdown_msg)
            print("\n✅ Kapanış mesajı gönderildi!")
            print("👋 Program sonlandırıldı.\n")
            break
            
        except Exception as e:
            print(f"\n❌ HATA OLUŞTU: {e}")
            print("⚠️ 10 saniye sonra yeniden denenecek...\n")
            time.sleep(10)
            continue

# ================== PROGRAM SONU ==================
"""
🎯 ÜLGEN v30.0 - ULTIMUS MAXIMUS

📋 ÖZELLİKLER:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Tüm analiz TEK MESAJDA toplanmış
✅ ADX Filtresi ile yatay piyasa koruması
✅ Parsiyel Kar Alımı (%3 karda %50 kapatır)
✅ İzleyen Stop (Kârı takip eder)
✅ Haber Duyarlılık Analizi (AI Sentiment)
✅ BTC Korelasyon ve Zaman Filtresi
✅ Her mesajın sonunda terim açıklamaları

📊 KULLANIM:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Tüm 5 parçayı tek dosyaya kopyalayın
2. `python ulgen_v27.py` ile çalıştırın
3. Her 15 dakikada bir Telegram'da tam rapor alın

🔧 KURULUM:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
pip install requests pandas numpy matplotlib

⚙️ AYARLAR (Kod başında):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TELEGRAM_TOKEN = "Kendi token'ınız"
CHAT_ID = "@YourChannel"
COINS = ["BTCUSDT", "ETHUSDT", "TAOUSDT"]
LEVERAGE = 10

💡 GÜVEN PUANI AÇIKLAMA:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
85-95: Çok güçlü - Tüm sinyaller uyumlu
75-84: Güçlü - Çoğu faktör lehimizde
65-74: Orta - Makul seviye
55-64: Zayıf - Az destekleyici sinyal
50-54: Çok zayıf - Sinyaller çelişkili

🧱 S1 (DESTEK) AÇIKLAMA:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Fiyatın tutunması beklenen kritik seviye
• Kırılırsa "ŞELALE" başlar (hızlı düşüş)
• Yakınında iseniz dikkatli olun
• Altına düşerse SHORT pozisyonu güçlenir

🕯️ MUM FORMASYONLARI:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Doji: Kararsızlık, trend dönüşü gelebilir
• Çekiç: Dip sinyali, yükseliş olabilir
• Yutan Boğa: Güçlü yükseliş, momentum bizde

👑 Ülgen Han - Trading Bot v30.0
"""