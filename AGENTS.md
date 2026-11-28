# CoinBot — Agent Kuralları
<!-- AUTO-BACKUP-RULE -->
## Zorunlu Yedekleme Kuralı (GitHub & Yerel Yedek)

Bu projede kod, yapılandırma veya dokümantasyon üzerinde herhangi bir güncelleme/değişiklik yapıldıktan sonra aşağıdaki yedekleme adımları **zorunlu olarak** uygulanmalıdır:

1. **GitHub'a Sürekli Yedekleme:**
   - Her güncelleme tamamlandığında değişiklikler gözden geçirilip anlamlı bir commit mesajıyla GitHub reposuna yedeklenmelidir (git add, git commit, git push).
   - .env, API anahtarları, token veya gizli kimlik bilgileri içeren dosyalar .gitignore kurallarına uygun olarak **asla** commit edilmemelidir.
2. **Yerel Disk Yedeklemesi (D:\uygulamalaryedekler):**
   - Yapılan güncellemelerden sonra proje klasörü güncel tarih formatıyla D:\uygulamalaryedekler\<KlasorAdi>_YYYY-MM-DD (ör. D:\uygulamalaryedekler\ProjeAdi_2026-11-28) konumuna da yedeklenmelidir.
