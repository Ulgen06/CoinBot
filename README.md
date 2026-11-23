# CoinBot (ÜLGEN)

Kripto haber, duygu analizi ve trading botu.

## Kurulum (macOS & Windows)

1. Repoyu klonlayın:
   ```bash
   git clone https://github.com/Ulgen06/CoinBot.git
   cd CoinBot
   ```

2. `.env.example` dosyasını `.env` olarak kopyalayıp API anahtarlarını doldurun:
   ```bash
   cp .env.example .env
   ```

3. Botu çalıştırın:
   ```bash
   cd bot1haber
   python3 run.py
   ```
   (Windows'ta `python run.py` veya `baslat.bat` kullanılabilir.)

## Güncelleme Alma

Yeni güncellemeleri çekmek için repo klasöründe:
```bash
git pull origin main
```

> Not: `.env`, `bot1haber/logs/` ve `bot1haber/data/` klasörlerindeki çalışma verileri `.gitignore` ile hariç tutulmuştur; bu sayede `git pull` sırasında kişisel verileriniz ve anahtarlarınız çakışmaz.
