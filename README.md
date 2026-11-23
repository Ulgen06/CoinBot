# CoinBot (ÜLGEN v31)

Kripto haber, duygu analizi, çoklu indikatörlü otomatik trading botu ve gerçek zamanlı Web Dashboard.

## Kurulum (macOS & Windows)

1. Repoyu klonlayın:
   ```bash
   git clone https://github.com/Ulgen06/CoinBot.git
   cd CoinBot
   ```

2. Gerekli Python paketlerini kurun:
   ```bash
   pip install -r requirements.txt
   ```

3. `.env.example` dosyasını `.env` olarak kopyalayıp API anahtarlarınızı girin:
   ```bash
   cp .env.example .env
   ```

4. Botu ve Web Dashboard'u (`http://localhost:9001`) başlatın:
   - **Windows:** `bot1haber/baslat.bat` (veya sessiz mod: `bot1haber/ULGEN_Gizli_Baslat.vbs`)
   - **macOS / Linux:**
     ```bash
     chmod +x bot1haber/baslat.sh
     ./bot1haber/baslat.sh
     ```

## Güncelleme Alma

Yeni güncellemeleri çekmek için repo klasöründe:
```bash
git pull origin main
```

> Not: `.env`, `bot1haber/logs/` ve `bot1haber/data/` klasörlerindeki çalışma verileri `.gitignore` ile hariç tutulmuştur; bu sayede `git pull` sırasında kişisel verileriniz ve anahtarlarınız çakışmaz.
