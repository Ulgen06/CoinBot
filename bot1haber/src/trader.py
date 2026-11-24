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

from logging.handlers import RotatingFileHandler

# Ensure logs directory exists
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

_log_fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_file_handler = RotatingFileHandler(
    os.path.join(log_dir, "trader_v2.log"),
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding='utf-8'
)
_file_handler.setFormatter(_log_fmt)
console = logging.StreamHandler()
console.setLevel(logging.WARNING)
console.setFormatter(_log_fmt)

_root_logger = logging.getLogger('')
_root_logger.setLevel(logging.INFO)
_root_logger.handlers.clear()
_root_logger.addHandler(_file_handler)
_root_logger.addHandler(console)
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

def get_config_path(filename):
    return os.path.join(get_base_dir(), 'config', filename)

def load_bot_config():
    """bot1haber/config/config.json ayarlarini canli olarak okur."""
    defaults = {
        "leverage": LEVERAGE,
        "risk_percent": 2,
        "stop_loss_pct": 2.0,
        "take_profit_pct": 5.0,
        "breakeven_pct": 1.3,
        "max_open_positions": 2,
        "cooldown_minutes": 60,
        "trader_mode": "Dengeli",
        "trailing_stop": True,
        "direction_bias": "SHORT"
    }
    try:
        cpath = get_config_path("config.json")
        if os.path.exists(cpath):
            with open(cpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    defaults.update(data)
    except Exception:
        pass
    return defaults

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
    """Cüzdan dosyasını güvenli okur; bozulursa otomatik yedekten geri yükler"""
    fpath = get_data_path(WALLET_FILE)
    backup_path = get_data_path("wallet.backup.json")
    lock_path = fpath + ".lock"
    
    # Simple lock mechanism
    start_time = time.time()
    while os.path.exists(lock_path):
        if time.time() - start_time > 5: # 5 second timeout
            try: os.remove(lock_path)
            except: pass
            break
        time.sleep(0.1)
        
    if os.path.exists(fpath):
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict) and 'available_balance' in data:
                return data
        except Exception as e:
            logging.warning(f"wallet.json okunamadı, yedek deneniyor: {e}")

    # Ana dosya yoksa veya bozuksa yedekten kurtar
    if os.path.exists(backup_path):
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict) and 'available_balance' in data:
                logging.warning("wallet.json yedekten (wallet.backup.json) kurtarıldı!")
                safe_save_wallet(data)
                return data
        except Exception as e:
            logging.error(f"wallet.backup.json okunamadı: {e}")
    return None

def safe_save_wallet(wallet):
    """Cüzdanı güvenli, atomik ve otomatik yedekli şekilde kaydeder"""
    if not isinstance(wallet, dict) or 'available_balance' not in wallet:
        return False
    fpath = get_data_path(WALLET_FILE)
    backup_path = get_data_path("wallet.backup.json")
    lock_path = fpath + ".lock"
    
    try:
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        # Create lock
        with open(lock_path, 'w') as f: f.write(str(os.getpid()))
        
        temp_file = fpath + ".tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(wallet, f, indent=4, ensure_ascii=False)
        os.replace(temp_file, fpath)

        # Atomik yedek kopyası
        temp_bak = backup_path + ".tmp"
        with open(temp_bak, 'w', encoding='utf-8') as f:
            json.dump(wallet, f, indent=4, ensure_ascii=False)
        os.replace(temp_bak, backup_path)
        
        # Remove lock
        if os.path.exists(lock_path): os.remove(lock_path)
        return True
    except Exception as e:
        print(f"❌ Kayıt Hatası: {e}")
        if os.path.exists(lock_path): os.remove(lock_path)
        return False
# ================== TELEGRAM FONKSİYONLARI ==================
def send_telegram_photo(photo_path, caption, silent=False):
    """Grafik görselini Telegram'a gönderir ve HTTP durumunu doğrular"""
    if not TELEGRAM_TOKEN:
        logging.error("Telegram Photo Hatası: TELEGRAM_TOKEN tanımlı değil.")
        return False
    try:
        with open(photo_path, 'rb') as f:
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
                data={
                    'chat_id': CHAT_ID,
                    'caption': caption[:1024],
                    'parse_mode': 'Markdown',
                    'disable_notification': str(bool(silent)).lower()
                },
                files={'photo': f},
                timeout=20
            )
        if r.status_code == 200 and r.json().get("ok"):
            logging.info(f"Foto gönderildi: {photo_path}")
            return True
        logging.error(f"Telegram Photo Hatası: {r.status_code} - {r.text[:200]}")
        return False
    except Exception as e:
        logging.error(f"Foto Gönderilemedi: {e}")
        return False

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

def send_telegram_message(message, silent=False):
    """Mesaj gönderir, HTTP durumunu doğrular, gerekirse düz metne düşer ve uzun mesajları böler"""
    if not TELEGRAM_TOKEN:
        logging.error("Telegram Mesaj Hatası: TELEGRAM_TOKEN tanımlı değil.")
        return False

    # Telegram 4096 karakter sınırı koruması
    chunks = []
    remaining = str(message)
    while len(remaining) > 4000:
        split_at = remaining.rfind("\n", 0, 4000)
        if split_at == -1:
            split_at = 4000
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip("\n")
    if remaining:
        chunks.append(remaining)

    all_ok = True
    for idx, chunk in enumerate(chunks):
        try:
            logging.info(f"Sending Trader message ({idx+1}/{len(chunks)}): {chunk[:50]}...")
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    'chat_id': CHAT_ID,
                    'text': chunk,
                    'parse_mode': 'Markdown',
                    'disable_notification': bool(silent)
                },
                timeout=15
            )
            if r.status_code == 200 and r.json().get("ok"):
                logging.info("Trader message sent.")
                continue

            # Markdown parse hatası (400) ise düz metin olarak tekrar dene
            if r.status_code == 400:
                logging.warning(f"Markdown reddedildi ({r.text[:160]}), düz metin deneniyor...")
                r2 = requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={'chat_id': CHAT_ID, 'text': chunk, 'disable_notification': bool(silent)},
                    timeout=15
                )
                if r2.status_code == 200 and r2.json().get("ok"):
                    logging.info("Trader message sent (plain fallback).")
                    continue
                logging.error(f"Telegram Düz Metin Hatası: {r2.status_code} - {r2.text[:200]}")
                all_ok = False
            else:
                logging.error(f"Telegram API Hatası: {r.status_code} - {r.text[:200]}")
                all_ok = False
        except Exception as e:
            logging.error(f"Telegram Bağlantı Hatası: {e}")
            all_ok = False
    return all_ok
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
        
        pos_lev = max(1, int(pos.get('leverage', LEVERAGE)))
        # Kar/Zarar Hesaplama (Kaldıraçlı)
        if pos['type'] == 'LONG':
            pnl_pct = ((curr - pos['entry']) / pos['entry']) * pos_lev
        else:  # SHORT
            pnl_pct = ((pos['entry'] - curr) / pos['entry']) * pos_lev
            
        pnl_usd = pos['amount'] * pnl_pct
        
        margin_used += pos['amount']
        unrealized_pnl += pnl_usd
        
        icon = "🟢" if pnl_usd >= 0 else "🔴"
        side_icon = "🔻" if pos['type'] == 'SHORT' else "🔺"
        source = pos.get('source', 'Manuel')
        source_badge = "🤖" if "Otomatik" in str(source) else "👤"
        
        # Hedef Seviyeleri (Stratejiye göre)
        tp1 = pos['entry'] * (1.03 if pos['type'] == 'LONG' else 0.97)
        sl = pos.get('stop_loss', 0)
        
        pos_details += f"{side_icon} *{symbol}* `{pos['type']} x{pos_lev}` {source_badge}\n"
        pos_details += f"   Giriş: `{pos['entry']:.2f}$` → Şimdi: `{curr:.2f}$`\n"
        pos_details += f"   SL: `{sl:.2f}$` | TP1: `{tp1:.2f}$` | Marjin: `{pos['amount']:.1f}$`\n"
        pos_details += f"   {icon} *PNL:* `{pnl_usd:+.2f}$` (`%{pnl_pct*100:+.1f}`)\n\n"

    equity = available + margin_used + unrealized_pnl
    init_bal = float(wallet.get('initial_balance', INITIAL_BALANCE) or INITIAL_BALANCE)
    total_pnl = equity - init_bal
    total_pnl_pct = (total_pnl / init_bal * 100) if init_bal > 0 else 0.0
    pnl_color = "🟢" if total_pnl >= 0 else "🔴"

    # Winrate hesabı (kapalı işlem geçmişinden)
    history = wallet.get('trade_history', [])
    closed_trades = [t for t in history if isinstance(t, dict) and 'pnl_usd' in t]
    total_closed = len(closed_trades)
    wins = sum(1 for t in closed_trades if float(t.get('pnl_usd', 0)) > 0)
    winrate_str = f"`%{(wins / total_closed) * 100:.1f}` ({wins}W/{total_closed - wins}L)" if total_closed > 0 else "`Henüz yok`"
    
    msg = f"💼 *PORTFÖY* (Başlangıç: `{init_bal:.0f}$`)\n"
    msg += f"   💰 Varlık: `{equity:.2f}$` | Nakit: `{available:.2f}$`\n"
    msg += f"   {pnl_color} K/Z: `{total_pnl:+.2f}$` (`%{total_pnl_pct:+.1f}`) | 🏆 Winrate: {winrate_str}\n"
    
    if pos_details: 
        msg += "\n" + pos_details.rstrip() + "\n"
    else: 
        if idle_reason:
            msg += f"⏸️ _Nakitte:_\n{idle_reason}\n"
        else:
            msg += "⏸️ _Nakitte — uygun fırsat bekleniyor._\n"
    
    return msg, equity

def manage_trade(symbol, signal, price, atr=0, reasons=[]):
    """İşlem açar/kapatır ve Trailing Stop/Partial TP/config.json risk kurallarını yönetir"""
    wallet = safe_load_wallet()
    if not wallet: return None

    # Yeni otomatik işlem sadece COINS listesindekiler için açılır;
    # ancak mevcut açık pozisyonlar (webden manuel açılanlar dahil) HER ZAMAN yönetilir!
    is_open = symbol in wallet.get('positions', {})
    if not is_open and symbol not in COINS:
        return None

    cfg = load_bot_config()
    cfg_lev = max(1, int(cfg.get('leverage', LEVERAGE)))
    cfg_sl_pct = max(0.5, float(cfg.get('stop_loss_pct', 2.0))) / 100.0
    cfg_tp_pct = max(1.0, float(cfg.get('take_profit_pct', 5.0))) / 100.0
    cfg_be_pct = max(0.6, float(cfg.get('breakeven_pct', 1.3))) / 100.0
    cfg_max_pos = max(1, int(cfg.get('max_open_positions', 2)))
    cfg_cooldown_sec = max(5, int(cfg.get('cooldown_minutes', 60))) * 60
    cfg_trailing = bool(cfg.get('trailing_stop', True))
    cfg_risk_pct = max(0.5, min(10.0, float(cfg.get('risk_percent', 2))))
    mode = str(cfg.get('trader_mode', 'Dengeli'))
    mode_margin_cap = {"Muhafazakar": 0.15, "Dengeli": 0.25, "Agresif": 0.35}.get(mode, 0.25)

    log = ""
    close_condition = False
    stop_hit = False
    reason = ""

    # Mevcut pozisyon varsa yönet
    if is_open:
        pos = wallet['positions'][symbol]
        pos_lev = max(1, int(pos.get('leverage', cfg_lev)))

        # Ham fiyat PNL yüzdesi (kaldıraçsız)
        pnl_now = ((price - pos['entry']) / pos['entry']) if pos['type'] == 'LONG' else ((pos['entry'] - price) / pos['entry'])

        # 0. Erken Breakeven (Fiyat %1.3 lehimize gidince Stop → Giriş, kârı zarara çevirme!)
        if 'breakeven_hit' not in pos and pnl_now >= cfg_be_pct:
            pos['breakeven_hit'] = True
            if pos['type'] == 'LONG':
                pos['stop_loss'] = max(pos.get('stop_loss', 0), pos['entry'] * 1.001)
            else:
                cur_sl = pos.get('stop_loss', 0)
                pos['stop_loss'] = min(cur_sl, pos['entry'] * 0.999) if cur_sl > 0 else pos['entry'] * 0.999
            log += f"🛡️ *BREAKEVEN AKTİF:* `{symbol}` (Stop → Giriş: `{pos['stop_loss']:.2f}$`)\n"

        # 1. Kademeli Kar Alım (Partial TP - hedef TP'nin %50'sinde %50 kar al + breakeven)
        partial_trigger = max(0.022, cfg_tp_pct * 0.5)
        if 'partial_tp_hit' not in pos and pnl_now >= partial_trigger:
            half_margin = pos['amount'] * 0.5
            profit_usd = half_margin * (pnl_now * pos_lev)
            wallet['available_balance'] += half_margin + profit_usd
            wallet['total_profit'] = wallet.get('total_profit', 0) + profit_usd
            pos['amount'] *= 0.5
            pos['partial_tp_hit'] = True
            pos['breakeven_hit'] = True
            # Stop'u giriş fiyatına çek (Risk-free / Breakeven)
            if pos['type'] == 'LONG':
                pos['stop_loss'] = max(pos.get('stop_loss', 0), pos['entry'] * 1.001)
            else:
                cur_sl = pos.get('stop_loss', 0)
                pos['stop_loss'] = min(cur_sl, pos['entry'] * 0.999) if cur_sl > 0 else pos['entry'] * 0.999
            log += f"🎯 *KISMİ KAR ALINDI (%50):* `{symbol}` | PNL: `{profit_usd:+.2f}$` (Stop → Giriş)\n"

        # 2. İzleyen Stop (Trailing Stop - config'den kontrol edilir)
        trail_trigger = max(0.025, cfg_tp_pct * 0.8)
        if cfg_trailing and pnl_now >= trail_trigger:
            trail_dist = min(0.02, max(0.008, cfg_sl_pct * 0.7))
            new_sl = price * (1 - trail_dist) if pos['type'] == 'LONG' else price * (1 + trail_dist)
            if pos['type'] == 'LONG':
                if new_sl > pos.get('stop_loss', 0):
                    pos['stop_loss'] = new_sl
            else:
                cur_sl = pos.get('stop_loss', 0)
                if cur_sl == 0 or new_sl < cur_sl:
                    pos['stop_loss'] = new_sl

        # 3. Kâr Alma (Take Profit - config'den okunan hedefin 2 katı veya min %15)
        full_tp_trigger = max(cfg_tp_pct * 2.0, 0.10)
        if pnl_now >= full_tp_trigger:
            close_condition = True
            reason = f"💰 KAR ALINDI (%{pnl_now*100:.1f})"

        # 4. Ters Sinyal ile Kapatma
        if not close_condition:
            close_condition = (pos['type'] == 'LONG' and signal == 'SAT') or \
                              (pos['type'] == 'SHORT' and signal == 'AL')

        # 5. Stop Loss veya Likidasyon Kontrolü
        sl_level = pos.get('stop_loss', 0)
        if sl_level > 0:
            if (pos['type'] == 'LONG' and price <= sl_level) or \
               (pos['type'] == 'SHORT' and price >= sl_level):
                stop_hit = True
        if pnl_now * pos_lev <= -0.95:
            stop_hit = True
            reason = "💀 LİKİDASYON KORUMASI"

        if close_condition or stop_hit:
            pnl_pct = pnl_now * pos_lev
            # Likidasyon koruması: zarar marjini aşamaz
            profit = max(-pos['amount'], pos['amount'] * pnl_pct)
            wallet['available_balance'] += max(0.0, pos['amount'] + profit)
            wallet['total_profit'] = wallet.get('total_profit', 0) + profit

            if stop_hit and not reason:
                reason = "🛑 STOP OLDU"
            elif not reason:
                reason = "💰 KAPAT"

            # İşlem geçmişine kaydet (Web Dashboard istatistikleri için)
            if 'trade_history' not in wallet:
                wallet['trade_history'] = []
            wallet['trade_history'].append({
                'timestamp': time.time(),
                'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'symbol': symbol,
                'type': f"{pos['type']} ({reason})",
                'entry': pos['entry'],
                'price': price,
                'amount': pos['amount'],
                'total': round(pos['amount'] + profit, 2),
                'pnl_usd': round(profit, 2),
                'leverage': pos_lev,
                'source': pos.get('source', 'Otomatik')
            })
            wallet['trade_history'] = wallet['trade_history'][-200:]

            del wallet['positions'][symbol]
            # Stop ile kapandıysa soğuma süresi (revenge trade koruması)
            if stop_hit and profit < 0:
                wallet.setdefault('cooldowns', {})[symbol] = time.time() + cfg_cooldown_sec
            log += f"[{reason}]: `{symbol}` Finansal: `{profit:+.2f}$` (%{pnl_pct*100:.2f})"

            # PNL Kartı Oluştur ve Gönder
            try:
                card_path = generate_pnl_card(
                    symbol, pos['type'], pos['entry'], price,
                    profit, pnl_pct, pos_lev
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
        if 0 <= hour <= 4 and mode != "Agresif":
            return f"⏳ `{symbol}` Pasif Saatler (00-04). İşlem Açılmadı."

        # Korelasyon & Maksimum Açık Pozisyon Limiti
        if len(wallet.get('positions', {})) >= cfg_max_pos:
            return f"🔒 `{symbol}` Maks. açık pozisyon ({cfg_max_pos}) dolu. İşlem açılmadı."

        # Stop Sonrası Soğuma Süresi (Cooldown)
        cd_until = float(wallet.get('cooldowns', {}).get(symbol, 0) or 0)
        if time.time() < cd_until:
            rem_min = int((cd_until - time.time()) // 60) + 1
            return f"❄️ `{symbol}` Stop sonrası soğuma süresinde ({rem_min} dk kaldı)."

        # Sabit Risk Bazlı Pozisyon Boyutlandırma (işlem başına kasanın max %risk_percent'i)
        safe_atr = atr if (atr and atr > 0) else (price * 0.01)
        atr_dist = min(price * cfg_sl_pct * 1.5, max(price * 0.008, 2.0 * safe_atr))
        sl_ratio = max(0.008, atr_dist / price)
        total_equity = wallet['available_balance'] + sum(p.get('amount', 0) for p in wallet.get('positions', {}).values())
        risk_usd = total_equity * (cfg_risk_pct / 100.0)
        notional = risk_usd / sl_ratio
        target_margin = notional / cfg_lev
        margin = min(wallet['available_balance'] * mode_margin_cap, target_margin)
        if margin > 10:
            wallet['available_balance'] -= margin
            sl = price - atr_dist if signal == "AL" else price + atr_dist

            wallet['positions'][symbol] = {
                "type": "LONG" if signal == "AL" else "SHORT",
                "entry": price,
                "amount": round(margin, 2),
                "leverage": cfg_lev,
                "stop_loss": sl,
                "source": "Otomatik",
                "time": datetime.now().strftime('%H:%M:%S')
            }
            log = f"🎰 *GİRİŞ:* `{symbol}` {signal} (x{cfg_lev} | Mod: {mode})\n"
            log += f"🛡️ İlk Stop: `{sl:.2f}$` | Giriş: `{price:.2f}$` | Marjin: `{margin:.2f}$`\n"
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
        
        # BTC Dominans (Önce hızlı CoinLore, yedek olarak CoinGecko)
        btc_d = None
        cl = robust_json_get("https://api.coinlore.net/api/global/", timeout=6)
        if isinstance(cl, list) and len(cl) > 0 and 'btc_d' in cl[0]:
            try:
                btc_d = float(cl[0]['btc_d'])
            except Exception:
                btc_d = None
        if btc_d is None:
            cg = robust_json_get("https://api.coingecko.com/api/v3/global", timeout=6)
            if cg and 'data' in cg and 'market_cap_percentage' in cg['data']:
                btc_d = float(cg['data']['market_cap_percentage']['btc'])
        if btc_d is None:
            return msg + "📊 *BTC DOMINANS:* `⚠️ Veri Hatası`"
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
    """Mum formasyonu analizi (Boğa + Ayı simetrik)"""
    if len(df) < 2:
        return ""

    row = df.iloc[-1]
    prev = df.iloc[-2]
    body = abs(row['c'] - row['o'])
    total_range = row['h'] - row['l']
    if total_range <= 0:
        return ""

    # Doji - Kararsızlık
    if body < total_range * 0.1:
        return "🕯️ Doji"

    # Yutan Boğa - Güçlü yükseliş
    if row['c'] > row['o'] and prev['c'] < prev['o'] and row['c'] > prev['o'] and row['o'] <= prev['c']:
        return "🔥 YutanB"

    # Yutan Ayı - Güçlü düşüş
    if row['c'] < row['o'] and prev['c'] > prev['o'] and row['c'] < prev['o'] and row['o'] >= prev['c']:
        return "🩸 YutanA"

    # Çekiç - Dip sinyali
    lower_wick = min(row['c'], row['o']) - row['l']
    upper_wick = row['h'] - max(row['c'], row['o'])
    if lower_wick > body * 2 and upper_wick < body:
        return "🔨 Çekiç"

    # Kayan Yıldız - Tepe sinyali
    if upper_wick > body * 2 and lower_wick < body:
        return "🌠 KayanY"

    return ""

# ================== ANA ANALİZ MOTORU ==================
def analyze_tf(symbol, tf):
    """Gelişmiş teknik analiz (Wilder RSI, ATR, ADX/+DI/-DI, MACD, EMA20/50/65/200, Hacim)"""
    try:
        limit = 220 if tf != "1M" else 50
        k = robust_json_get(
            "https://fapi.binance.com/fapi/v1/klines",
            params={'symbol': symbol, 'interval': tf, 'limit': limit}
        )
        if not k or len(k) < 30:
            return None

        df = pd.DataFrame(k, columns=['t','o','h','l','c','v','x','q','n','tb','tq','i']).astype(float)
        cur, prev = df['c'].iloc[-1], df['c'].iloc[-2]

        # 1. Wilder's RSI (TradingView/Binance uyumlu)
        delta = df['c'].diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = (100 - (100 / (1 + rs))).fillna(100)

        # 2. Wilder's ATR
        df['tr'] = pd.concat([
            df['h'] - df['l'],
            (df['h'] - df['c'].shift()).abs(),
            (df['l'] - df['c'].shift()).abs()
        ], axis=1).max(axis=1)
        df['atr'] = df['tr'].ewm(alpha=1/14, adjust=False).mean()

        # 3. Wilder's ADX (+DI / -DI)
        up_move = df['h'].diff()
        dn_move = -df['l'].diff()
        plus_dm = pd.Series(np.where((up_move > dn_move) & (up_move > 0), up_move, 0.0), index=df.index)
        minus_dm = pd.Series(np.where((dn_move > up_move) & (dn_move > 0), dn_move, 0.0), index=df.index)
        atr_safe = df['atr'].replace(0, np.nan)
        plus_di = 100 * (plus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_safe)
        minus_di = 100 * (minus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_safe)
        di_sum = (plus_di + minus_di).replace(0, np.nan)
        dx = (100 * (plus_di - minus_di).abs() / di_sum).fillna(0)
        df['adx'] = dx.ewm(alpha=1/14, adjust=False).mean()

        # 4. MACD (12, 26, 9)
        ema12 = df['c'].ewm(span=12, adjust=False).mean()
        ema26 = df['c'].ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        macd_sig = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - macd_sig
        macd_cross = ""
        if macd_line.iloc[-2] <= macd_sig.iloc[-2] and macd_line.iloc[-1] > macd_sig.iloc[-1]:
            macd_cross = "BULL"
        elif macd_line.iloc[-2] >= macd_sig.iloc[-2] and macd_line.iloc[-1] < macd_sig.iloc[-1]:
            macd_cross = "BEAR"

        # 5. EMA Katmanları
        ema20 = df['c'].ewm(span=20, adjust=False).mean().iloc[-1]
        ema50 = df['c'].ewm(span=50, adjust=False).mean().iloc[-1]
        ema65 = df['c'].ewm(span=65, adjust=False).mean().iloc[-1]
        ema200 = df['c'].ewm(span=200, adjust=False).mean().iloc[-1] if len(df) >= 200 else ema50

        # 6. Bollinger Squeeze & Hacim Oranı
        bb_mean = df['c'].rolling(20).mean().iloc[-1]
        bb_std = df['c'].rolling(20).std().iloc[-1]
        bb_width = (bb_std * 4 / bb_mean) if bb_mean else 0
        vol_avg = df['v'].rolling(20).mean().iloc[-1]
        vol_ratio = (df['v'].iloc[-1] / vol_avg) if (vol_avg and vol_avg > 0) else 1.0

        return {
            "rsi": float(df['rsi'].iloc[-1]),
            "adx": float(df['adx'].iloc[-1]) if not np.isnan(df['adx'].iloc[-1]) else 0.0,
            "plus_di": float(plus_di.iloc[-1]) if not np.isnan(plus_di.iloc[-1]) else 0.0,
            "minus_di": float(minus_di.iloc[-1]) if not np.isnan(minus_di.iloc[-1]) else 0.0,
            "macd_hist": float(macd_hist.iloc[-1]),
            "macd_cross": macd_cross,
            "trend": "📈" if cur > ema50 else "📉",
            "c": cur, "prev": prev,
            "ema20": ema20,
            "ema50": ema50,
            "ema65": ema65,
            "ema200": ema200,
            "sq": bool(bb_width < 0.015),
            "wh": bool(vol_ratio > 2.2),
            "vol_ratio": float(vol_ratio),
            "fvg": check_fvg(df), "div": check_divergence(df), "candle": check_candles(df),
            "atr": float(df['atr'].iloc[-1])
        }
    except Exception as e:
        print(f"Analiz hatası ({symbol} {tf}): {e}")
        return None

# ================== STRATEJİ & KARAR MEKANİZMASI (v31 SUPER ENGINE) ==================
def generate_strategy(rsi15, rsi4h, price, s1, r1, trend4h, candle, atr, div, fvg, is_squeeze,
                      adx=0, btc_trend="", ema50=0, ema65=0, ema200=0,
                      macd_hist=0, macd_cross="", vol_ratio=1.0, plus_di=0, minus_di=0,
                      funding_rate=0.0, news_sent="", trend1h=""):
    """
    ÜLGEN v31 Çok Katmanlı Simetrik Strateji Motoru (LONG + SHORT)
    """
    cfg = load_bot_config()
    mode = str(cfg.get('trader_mode', 'Dengeli'))
    direction_bias = str(cfg.get('direction_bias', 'SHORT')).upper()
    min_adx = {"Muhafazakar": 24, "Dengeli": 20, "Agresif": 16}.get(mode, 20)
    min_conf = {"Muhafazakar": 76, "Dengeli": 68, "Agresif": 58}.get(mode, 68)

    signal = "NÖTR"
    desc = "Piyasa şu an dinleniyor."
    stop_level = 0
    bull_score = 50
    bear_score = 50
    bull_reasons = []
    bear_reasons = []

    # SHORT ağırlıklı mod: SHORT kurulumlarına öncelik, LONG için ekstra yüksek onay eşiği
    if direction_bias == "SHORT":
        bear_score += 6
        short_min_conf = max(56, min_conf - 4)
        long_min_conf = min(92, min_conf + 14)
    elif direction_bias == "LONG":
        bull_score += 6
        long_min_conf = max(56, min_conf - 4)
        short_min_conf = min(92, min_conf + 14)
    else:
        short_min_conf = min_conf
        long_min_conf = min_conf

    logic_diagnostics = {
        "adx_val": adx,
        "adx_status": "GÜÇLÜ TREND" if adx > 25 else ("ZAYIF TREND" if adx > min_adx else "YATAY PİYASA"),
        "btc_corr": "UYUMLU ✅" if btc_trend == trend4h else "ZIT ⚠️",
        "time_filter": "AKTİF ✅" if not (0 <= datetime.now().hour <= 4) else "PASİF ⏳",
        "volatility": "NORMAL" if (price > 0 and atr / price < 0.05) else "YÜKSEK 🔥",
        "mode": mode,
        "bias": direction_bias
    }

    # 1. ADX Yatay Piyasa Filtresi
    if adx < min_adx:
        return "NÖTR", f"📉 Yatay Piyasa (ADX:{adx:.1f} < {min_adx}). Trend onayı bekleniyor.", 0, logic_diagnostics, []

    # 2. Ana Trend (4H EMA50 & EMA200)
    if trend4h == "📈":
        bull_score += 14
        bear_score -= 10
        bull_reasons.append("4H Ana Trend Pozitif (EMA50 Üzeri)")
    else:
        bear_score += 14
        bull_score -= 10
        bear_reasons.append("4H Ana Trend Negatif (EMA50 Altı)")

    if ema200 > 0:
        if price > ema200:
            bull_score += 6
            bull_reasons.append("EMA200 Üzerinde (Makro Boğa)")
        else:
            bear_score += 6
            bear_reasons.append("EMA200 Altında (Makro Ayı)")

    # 3. Directional Index (+DI vs -DI)
    if plus_di > minus_di and adx > 25:
        bull_score += 8
        bull_reasons.append(f"Alıcı Baskın (+DI:{plus_di:.0f} > -DI:{minus_di:.0f})")
    elif minus_di > plus_di and adx > 25:
        bear_score += 8
        bear_reasons.append(f"Satıcı Baskın (-DI:{minus_di:.0f} > +DI:{plus_di:.0f})")

    # 4. MACD Momentum
    if macd_cross == "BULL":
        bull_score += 12
        bull_reasons.append("MACD Boğa Kesişimi 📈")
    elif macd_hist > 0:
        bull_score += 5
    elif macd_cross == "BEAR":
        bear_score += 12
        bear_reasons.append("MACD Ayı Kesişimi 📉")
    elif macd_hist < 0:
        bear_score += 5

    # 5. BTC Korelasyonu
    if btc_trend == "📈":
        bull_score += 6
        bear_score -= 12
    elif btc_trend == "📉":
        bear_score += 6
        bull_score -= 12

    # 6. Mum Formasyonları (Simetrik)
    c_str = str(candle)
    if "Çekiç" in c_str or "YutanB" in c_str:
        bull_score += 12
        bull_reasons.append(f"Boğa Mum Formasyonu: {candle}")
    elif "KayanY" in c_str or "YutanA" in c_str:
        bear_score += 12
        bear_reasons.append(f"Ayı Mum Formasyonu: {candle}")

    # 7. RSI Divergence & FVG
    if "PU" in str(div):
        bull_score += 10
        bull_reasons.append("RSI Pozitif Uyumsuzluk (Dönüş)")
    elif "NU" in str(div):
        bear_score += 10
        bear_reasons.append("RSI Negatif Uyumsuzluk (Düşüş)")

    if "🟢" in str(fvg):
        bull_score += 5
        bull_reasons.append("Boğa FVG Desteği")
    elif "🔴" in str(fvg):
        bear_score += 5
        bear_reasons.append("Ayı FVG Direnci")

    # 8. Hacim Onayı
    if vol_ratio >= 1.6:
        if bull_score >= bear_score:
            bull_score += 8
            bull_reasons.append(f"Güçlü Hacim Onayı ({vol_ratio:.1f}x)")
        else:
            bear_score += 8
            bear_reasons.append(f"Güçlü Satış Hacmi ({vol_ratio:.1f}x)")

    # 9. Funding Rate & Haber Duygusu Filtresi
    if funding_rate > 0.0005:  # Aşırı kalabalık LONG
        bull_score -= 8
        bear_score += 4
    elif funding_rate < -0.0005:  # Aşırı kalabalık SHORT
        bear_score -= 8
        bull_score += 4

    if "BOĞA" in str(news_sent):
        bull_score += 5
        bull_reasons.append("Haber Duygusu Pozitif")
    elif "AYI" in str(news_sent) or "PANİK" in str(news_sent):
        bear_score += 5
        bear_reasons.append("Haber Duygusu Negatif")

    if is_squeeze:
        bull_score -= 6
        bear_score -= 6

    bull_conf = max(35, min(95, bull_score))
    bear_conf = max(35, min(95, bear_score))
    margin = 0.004

    # ══════════════════ KARAR MATRİSİ (SHORT ÖNCELİKLİ + 1H ONAYI + SQUEEZE KORUMASI) ══════════════════
    short_1h_ok = (not trend1h) or (trend1h == "📉")
    long_1h_ok = (not trend1h) or (trend1h == "📈")

    # Dipte SHORT kovalamama (Short-Squeeze Koruması: 15m RSI < 32 aşırı satım)
    if trend4h == "📉" and rsi15 < 32 and bear_conf >= short_min_conf:
        desc = f"🛡️ Short-Squeeze Koruması (15D RSI:{rsi15:.0f} aşırı satım — tepki/pullback bekleniyor)"
        return "NÖTR", desc, 0, logic_diagnostics, []

    # 1. BREAKOUT SHORT (Destek kırılımı + 4H & 1H uyumu)
    if s1 > 0 and price < s1 * (1 - margin) and trend4h == "📉" and short_1h_ok and bear_conf >= short_min_conf:
        signal = "SAT"
        desc = f"🚨 *BREAKOUT SHORT:* S1 Kırıldı (Güven: %{bear_conf})"
        bear_reasons.append(f"S1 Desteği Kırıldı ({s1:.2f}$) + 4H/1H Düşüş")
        stop_level = price + (1.5 * atr)
        return signal, desc, stop_level, logic_diagnostics, bear_reasons

    # 2. TEPE / OVERBOUGHT SHORT (Direnç + aşırı alım + 4H & 1H uyumu)
    if rsi15 > 64 and trend4h == "📉" and short_1h_ok and bear_conf >= short_min_conf and ((r1 > 0 and price >= r1 * 0.985) or (ema50 > 0 and price >= ema50 * 0.992)):
        signal = "SAT"
        desc = f"🔴 *TEPE / PULLBACK SHORT:* Direnç + Aşırı Alım (Güven: %{bear_conf})"
        bear_reasons.append(f"RSI Yüksek ({rsi15:.0f}) + Direnç/EMA50 Bölgesi")
        stop_level = price + (2.0 * atr)
        return signal, desc, stop_level, logic_diagnostics, bear_reasons

    # 3. TREND DEVAM SHORT (SHORT ağırlıklı modda 4H+1H düşüş + EMA50 altı)
    if direction_bias == "SHORT" and trend4h == "📉" and short_1h_ok and bear_conf >= (short_min_conf + 4) and (ema50 > 0 and price < ema50) and (40 <= rsi15 <= 64) and (minus_di > plus_di or macd_hist < 0):
        signal = "SAT"
        desc = f"🔻 *TREND SHORT:* 4H+1H Düşüş Devam (Güven: %{bear_conf})"
        bear_reasons.append("4H+1H Düşüş + EMA50 Altı + Satıcı Momentumu")
        stop_level = price + (1.8 * atr)
        return signal, desc, stop_level, logic_diagnostics, bear_reasons

    # 4. BREAKOUT LONG (SHORT ağırlıklı modda yalnızca çok güçlü makro boğa onayıyla)
    long_macro_ok = long_1h_ok and ((direction_bias != "SHORT") or (adx >= min_adx + 4 and btc_trend == "📈" and (ema200 <= 0 or price > ema200)))
    if long_macro_ok and r1 > 0 and price > r1 * (1 + margin) and trend4h == "📈" and bull_conf >= long_min_conf:
        signal = "AL"
        desc = f"🌊 *BREAKOUT LONG:* R1 Kırıldı (Güven: %{bull_conf})"
        bull_reasons.append(f"R1 Direnci Kırıldı ({r1:.2f}$)")
        stop_level = price - (1.5 * atr)
        return signal, desc, stop_level, logic_diagnostics, bull_reasons

    # 5. DİP / PULLBACK LONG (SHORT ağırlıklı modda çok yüksek eşikle)
    if long_macro_ok and rsi15 < 32 and trend4h == "📈" and bull_conf >= long_min_conf and ((s1 > 0 and price <= s1 * 1.015) or (ema50 > 0 and price <= ema50 * 1.008)):
        signal = "AL"
        desc = f"🟢 *DİP / PULLBACK LONG:* Destek + Aşırı Satım (Güven: %{bull_conf})"
        bull_reasons.append(f"RSI Aşırı Satım ({rsi15:.0f}) + Destek Bölgesi")
        stop_level = price - (2.0 * atr)
        return signal, desc, stop_level, logic_diagnostics, bull_reasons

    desc = f"⏸️ Beklemede (Ayı:%{bear_conf} [Eşik:%{short_min_conf}] | Boğa:%{bull_conf} [Eşik:%{long_min_conf}])"
    return signal, desc, stop_level, logic_diagnostics, []
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
        
        assets_dir = os.path.join(get_base_dir(), "assets")
        os.makedirs(assets_dir, exist_ok=True)
        fn = os.path.join(assets_dir, "dashboard_v30.png")
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
                ema50=d15.get('ema50', 0), ema65=d15.get('ema65', 0),
                ema200=d4h.get('ema200', 0),
                macd_hist=d15.get('macd_hist', 0), macd_cross=d15.get('macd_cross', ""),
                vol_ratio=d15.get('vol_ratio', 1.0),
                plus_di=d15.get('plus_di', 0), minus_di=d15.get('minus_di', 0),
                funding_rate=funding_rates.get(coin, 0.0),
                news_sent=news_sent,
                trend1h=d1h['trend'] if d1h else ""
            )
            coin_analyses[coin] = {
                's1': s1, 'r1': r1, 'd15': d15, 'd1h': d1h, 'd4h': d4h,
                'sig': sig, 'desc': desc, 'stop': stop, 'diag': diag, 'reasons': reasons
            }
            if sig == "NÖTR":
                min_adx_now = {"Muhafazakar": 24, "Dengeli": 20, "Agresif": 16}.get(diag.get('mode', 'Dengeli'), 20)
                if diag['adx_val'] < min_adx_now:
                    idle_reasons.append(f"   ➤ {coin}: Yatay Piyasa (ADX:{diag['adx_val']:.1f})")
                elif btc_trend_val != d4h['trend']:
                    idle_reasons.append(f"   ➤ {coin}: BTC Trendiyle Uyumsuz")
                else:
                    idle_reasons.append(f"   ➤ {coin}: Güçlü Sinyal Bekleniyor")

    # Cüzdan Raporu (Analizlerden gelen veriye göre)
    unique_idle = list(set(idle_reasons))[:3] # Çok kalabalık olmasın
    wallet_msg, equity = get_wallet_status(curr_prices, idle_reason="\n".join(unique_idle) if unique_idle else "")
    
    # ═══════════════════════════════════════
    # MESAJ BAŞLANGIÇ (TEMİZ VE KOMPAKT v31)
    # ═══════════════════════════════════════
    cfg_now = load_bot_config()
    bias_now = str(cfg_now.get('direction_bias', 'SHORT')).upper()
    bias_label = "🔻 SHORT Odaklı" if bias_now == "SHORT" else ("🔺 LONG Odaklı" if bias_now == "LONG" else "⚖️ Dengeli")
    now_str = datetime.now().strftime('%H:%M')

    msg = f"👑 *ÜLGEN v31 • PİYASA RAPORU* (`{now_str}`)\n"
    msg += f"🎯 *Strateji:* {bias_label} | *Mod:* `{cfg_now.get('trader_mode', 'Dengeli')}`\n"
    msg += f"📰 *Haber Duygusu:* `{news_sent}`\n"
    msg += f"{sentiment.strip()}\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    msg += wallet_msg
    msg += "━━━━━━━━━━━━━━━━━━\n\n"
    
    # En yüksek güven puanlı coinlere öncelik vererek (korelasyon/max pozisyon koruması) işlemleri yürüt
    trade_logs = {}
    if live_trade:
        def _sig_conf(c_name):
            a = coin_analyses.get(c_name)
            if not a or a['sig'] == "NÖTR":
                return -1
            m = re.search(r'%(\d+)', a['desc'])
            return int(m.group(1)) if m else 0
        for c_name in sorted(COINS, key=_sig_conf, reverse=True):
            a = coin_analyses.get(c_name)
            if a and a['sig'] != "NÖTR":
                trade_logs[c_name] = manage_trade(c_name, a['sig'], a['d15']['c'], a['d15']['atr'], reasons=a['reasons'])

    # ═══════════════════════════════════════
    # HER COİN İÇİN TAM & DÜZENLİ ANALİZ
    # ═══════════════════════════════════════
    for coin in COINS:
        analysis = coin_analyses.get(coin)
        if not analysis: continue

        s1, r1 = analysis['s1'], analysis['r1']
        d15, d4h = analysis['d15'], analysis['d4h']
        price = d15['c']
        
        fund_rate = funding_rates.get(coin, 0)
        fund_icon = "🟢" if fund_rate > 0 else "🔴" if fund_rate < 0 else "⚪"
        fund_bias = "Long baskısı" if fund_rate > 0 else ("Short baskısı" if fund_rate < 0 else "Nötr")
        
        msg += f"🪙 *{coin}* `{price:.2f}$` | {fund_icon} FR: `%{fund_rate*100:.3f}` ({fund_bias})\n"
        
        # Tüm 5 Timeframe (2 düzenli satırda: 15D/1S/4S ve 1G/1Ay)
        tf_cache = {"15m": analysis.get('d15'), "1h": analysis.get('d1h'), "4h": analysis.get('d4h')}
        tf_row1, tf_row2, notable = [], [], []
        for tf in TIMEFRAMES:
            d = tf_cache.get(tf) or analyze_tf(coin, tf)
            if d:
                tf_label = tf.replace("15m", "15D").replace("1h", "1S").replace("4h", "4S").replace("1d", "1G").replace("1M", "1Ay")
                icons = ""
                if d['rsi'] < 30: icons += "🚨"
                elif d['rsi'] > 70: icons += "⚠️"
                if d['sq']: icons += "💥"
                if d['wh']: icons += "🐋"
                if d['div']: icons += "🔄"
                if d['fvg']: icons += "🧲"
                cell = f"`{tf_label}` {d['trend']}{d['rsi']:.0f}{icons}"
                if tf in ["15m", "1h", "4h"]:
                    tf_row1.append(cell)
                else:
                    tf_row2.append(cell)

                if tf in ["15m", "1h", "4h"] and d.get('candle'):
                    notable.append(f"{tf_label}: {d['candle']}")
                if tf in ["15m", "1h"] and d.get('div'):
                    notable.append(f"{tf_label}: {d['div']}")
                if tf in ["15m", "1h"] and d.get('fvg'):
                    notable.append(f"{tf_label}: {d['fvg']}")

        if tf_row1:
            msg += "   " + " | ".join(tf_row1) + "\n"
        if tf_row2:
            msg += "   " + " | ".join(tf_row2) + "\n"
        if notable:
            msg += f"   🕯️ _{' • '.join(notable[:3])}_\n"

        # Seviyeler, S1 Şelale Riski & Stratejik Göstergeler
        sig, desc, stop, diag, reasons = analysis['sig'], analysis['desc'], analysis['stop'], analysis['diag'], analysis['reasons']
        s1_dist = ((price - s1) / s1 * 100) if s1 > 0 else 0
        s1_tag = f"⚠️ S1 altı (%{abs(s1_dist):.1f})" if price < s1 else (f"🟡 S1'e yakın (%{s1_dist:.1f})" if price <= s1 * 1.02 else f"✅ S1 üstü (+%{s1_dist:.1f})")
        msg += f"   🧱 S1: `{s1:.2f}$` | R1: `{r1:.2f}$` • {s1_tag}\n"
        msg += f"   🧠 ADX: `{diag['adx_val']:.1f}` ({diag['adx_status']}) | BTC: `{diag['btc_corr']}` | Vol: `{diag['volatility']}`\n"
        
        # Yön, Güven & Karar
        conf_match = re.search(r'%(\d+)', desc)
        conf_val = int(conf_match.group(1)) if conf_match else 0
        if sig == "SAT":
            direction = "🔴 *SHORT*"
        elif sig == "AL":
            direction = "🟢 *LONG*"
        else:
            direction = "⚪ *NÖTR*"
        
        msg += f"   {direction} — {desc}\n"
        if sig != "NÖTR" and conf_val:
            msg += f"   📊 _{explain_confidence(conf_val)}_\n"
        
        # Stop Loss & İşlem Yönetimi
        if sig != "NÖTR":
            msg += f"   🛡️ *Stop (ATR):* `{stop:.2f}$`\n"
            if live_trade:
                log = trade_logs.get(coin)
                if log: 
                    msg += f"\n{log}\n"
            else:
                msg += f"   ℹ️ _Test Modu: İşlem açılmadı._\n"
        
        msg += "\n"
    
    msg += f"━━━━━━━━━━━━━━━━━━\n🕒 `{now_str}` | _ÜLGEN v31 • BTC • ETH • TAO_"
    
    return msg

# ================== ANA PROGRAM DÖNGÜSÜ ==================
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 ÜLGEN v31.0 - SHORT ODAKLI TRADER AKTİF")
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
    cfg_start = load_bot_config()
    bias_start = str(cfg_start.get('direction_bias', 'SHORT')).upper()
    startup_msg = (
        f"🚀 *ÜLGEN v31 AKTİF*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Coinler:* `{', '.join(COINS)}`\n"
        f"🎯 *Odak:* `{'SHORT Ağırlıklı' if bias_start == 'SHORT' else bias_start}` | *Mod:* `{cfg_start.get('trader_mode', 'Dengeli')}`\n"
        f"⚡ *Kaldıraç:* `x{cfg_start.get('leverage', LEVERAGE)}` | *Rapor:* `Her 15 dk`\n"
        f"🛡️ *Koruma:* ADX, Kısmi Kar, İzleyen Stop & Haber Duygusu\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"_Piyasa takibi başladı._"
    )
    
    send_telegram_message(startup_msg, silent=True)
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
            # Her döngüde COINS + webden açılan tüm açık pozisyonların SL/TP kontrolü
            wallet_snapshot = safe_load_wallet() or {}
            monitored_symbols = list(dict.fromkeys(COINS + list(wallet_snapshot.get('positions', {}).keys())))
            for coin in monitored_symbols:
                try:
                    api_sym = coin if coin.endswith("USDT") else f"{coin}USDT"
                    p_data = robust_json_get(
                        f"https://fapi.binance.com/fapi/v1/ticker/price",
                        params={'symbol': api_sym},
                        timeout=3
                    )
                    if p_data and 'price' in p_data:
                        price = float(p_data['price'])
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
                
                # A. GÖRSEL ANALİZ GÖNDER (Rutin görsel sessiz)
                print("📊 Görsel dashboard oluşturuluyor...")
                img, cap = generate_dashboard_image()
                
                if img and cap:
                    print(f"   ✅ Görsel oluşturuldu: {img}")
                    send_telegram_photo(img, cap, silent=True)
                    print(f"   📤 Telegram'a gönderildi (sessiz)!")
                else:
                    print(f"   ⚠️ Görsel oluşturulamadı (atlanıyor)")
                
                # B. TAM RAPOR GÖNDER (İşlem açıldı/kapandıysa SESLİ, rutin raporsa SESSİZ)
                print("\n📝 Tam rapor oluşturuluyor...")
                report = generate_full_report(live_trade=True)
                has_trade_event = any(k in report for k in ("🎰 *GİRİŞ:", "🎯 *KISMİ KAR", "🛑 STOP", "💰 KAR ALINDI", "💀 LİKİDASYON"))
                
                print(f"   ✅ Rapor hazır ({len(report)} karakter)")
                send_telegram_message(report, silent=not has_trade_event)
                print(f"   📤 Telegram'a gönderildi ({'SESLİ - İŞLEM VAR' if has_trade_event else 'sessiz'})!")

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