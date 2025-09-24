🖼️ Görsel Denetleyici — Var/Yok + Kırık Bağlantı Kontrolü
==========================================================

Bu program, web sitelerindeki görsellerin varlık durumunu ve erişilebilirliğini otomatik olarak denetler.  
Sitemap üzerinden tüm sayfaları tarar, her sayfada hedef görselleri bulur ve kırık bağlantıları tespit eder.

✨ Ne İşe Yarar?
-----------------
• Web sitenizdeki görsellerin tamamının var olup olmadığını kontrol eder.  
• Kırık görsel linklerini (404 hataları veya erişilemeyen görseller) bulur.  
• Sayfa başına hangi görsellerin eksik veya erişilemez olduğunu raporlar.  
• SEO ve kullanıcı deneyimini geliştirmek için eksik görsellerin hızlı tespitini sağlar.  
• Sonuçları tablo ve CSV dosyası olarak sunar.

💡 Kullanım Senaryoları:
-------------------------
- 📸 Blog veya haber sitelerinde eksik görsel tespiti  
- 🛍️ E-ticaret sitelerinde ürün görsellerinin tamlık kontrolü  
- 🌍 Kurumsal sitelerde kırık bağlantıların düzenli takibi  
- ⚙️ Büyük sitelerde sitemap üzerinden toplu kalite kontrol

🔹 Program Ne Yapar?
---------------------
- Sitemap dosyasındaki tüm sayfaları otomatik tarar.  
- Öncelikli olarak `.post-image .post-image-inner img` alanındaki görselleri arar.  
- Eğer bulunamazsa, sayfadaki `<img>`, `og:image`, ve `rel=image_src` etiketlerini kontrol eder.  
- Her görsel için HTTP HEAD isteği gönderir:
  - 200 OK
  - Content-Type image/*
  - Content-Length > 0  
- Eğer HEAD isteği başarısız olursa GET isteği ile küçük bir parça indirerek doğrulama yapar.  
- Her sayfa için NoImage, BrokenImage, veya Sağlam olarak bayraklar üretir.

🔹 Bayraklar:
-------------
- NoImage ➡️ Sayfada hiç görsel bulunamadı veya sayfa erişilemedi  
- BrokenImage ➡️ Görsel var ama erişilemiyor / bozuk  
- "" (Boş) ➡️ Görsel sağlıklı

----------------------------------------------------------

⚙️ Sistem Gereksinimleri
-------------------------
• Python 3.10+ (zorunlu)  
• tkinter GUI için gerekli (Linux'ta kurulum: sudo apt install python3-tk)  
• İnternet bağlantısı (sayfalar ve görselleri kontrol etmek için)

----------------------------------------------------------

📥 Kurulum
----------
1️⃣ Sanal ortam oluşturun (önerilir)  
Windows:
python -m venv .venv
.venv\Scripts\activate

macOS/Linux:
python -m venv .venv
source .venv/bin/activate

2️⃣ Bağımlılıkları yükleyin
pip install -r requirements.txt

requirements.txt içeriği:
-------------------------
requests>=2.32.0
beautifulsoup4>=4.12.3
lxml>=5.3.0
ttkbootstrap>=1.10.1

3️⃣ Programı çalıştırın
python image_presence_checker.py

Varsayılan Sitemap URL:  
https://ebubekirbastama.com.tr/sitemap.xml
> Arayüz üzerinden farklı bir sitemap adresi girebilirsiniz.

----------------------------------------------------------

🚀 Kullanım Adımları
--------------------
1. Sitemap URL alanını kontrol edin (varsayılan hazır).  
2. İş parçacığı sayısını belirleyin (8 önerilir).  
3. İsterseniz “Sadece aynı domaindeki görseller” seçeneğini işaretleyin.  
4. “Sadece sorunlu sayfaları/görselleri göster” filtresini kullanarak problemli kayıtları öne çıkarın.  
5. “Taramayı Başlat” butonuna basarak süreci başlatın.  
6. İlerlemeyi durum çubuğu ve log ekranından takip edin.  
7. Tablodaki verileri CSV olarak dışa aktarabilirsiniz.  
8. Tablo satırına çift tıklayarak ilgili görseli veya sayfayı tarayıcıda açabilirsiniz.

----------------------------------------------------------

📊 CSV Çıktısı Açıklaması
-------------------------
- page_url ➡️ Sayfanın adresi  
- image_url ➡️ Görselin tam adresi (boş olabilir)  
- flags ➡️ NoImage, BrokenImage veya boş (sağlam)  
- detail ➡️ HTTP isteğinin sonucu (örn. HEAD OK 200 image/webp len=...)  
- error ➡️ Hata mesajı (varsa)


----------------------------------------------------------

📜 Lisans
---------
MIT License © Ebubekir Bastama
