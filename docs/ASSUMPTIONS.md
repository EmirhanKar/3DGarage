# MODIF-AI Mimari ve Lisanslama Varsayımları (ASSUMPTIONS.md)

Bu doküman, teknik olmayan yöneticiler ve ticari değerlendirme için hazırlanmıştır. Projedeki yapay zeka modelleri, harici servisler ve lisans riskleri burada açıklanmıştır.

---

## 1. Araç Tespit Servisi (`car_detection.py`) ve Lisans Analizi

### 1.1. Neden Araç Ön Kontrolü Yapmalıyız?
Tripo API, her 3D model üretiminde ücretli kredi kesmektedir. Kullanıcı yanlışlıkla bir kedi, manzara veya boş bir oda fotoğrafı yüklerse:
- Tripo API yine de kredi düşer veya başarısız olur,
- Kullanıcı boşuna beklemiş ve para/kredi kaybetmiş olur.
Bu nedenle fotoğrafta bir **"araba"** olup olmadığını kontrol eden yerel ve ücretsiz bir filtre (pre-check) koymak bütçeyi korur.

### 1.2. Mevcut Model Durumu: Keras / Stanford Cars
Mevcut kod tabanında MobileNetV2 tabanlı `araba_modeli_guclu_v2.keras` ve `cars_meta.mat` dosyaları bulunmaktadır.
- **Stanford Cars Veri Seti Kısıtlaması:** Stanford Cars veri seti orijinal olarak **yalnızca akademik ve ticari olmayan araştırma** amacıyla lisanslanmıştır. Ticari bir üründe bu ağırlıkları kullanmak telif hakkı riski taşır.

### 1.3. Ultralytics / YOLO Alternatifi ve AGPL-3.0 Lisans Riski
Birçok geliştirici araç tespiti için `ultralytics` (YOLOv8, YOLOv11 vb.) kütüphanesini tercih etmektedir. Ancak ticari kullanımda kritik bir hukuki kural vardır:
- **AGPL-3.0 Lisansı:** Ultralytics açık kaynak kodları AGPL-3.0 ile korunmaktadır. Eğer backend sunucunuzda Ultralytics YOLO kullanırsanız, AGPL gereği **tüm backend ve uygulamanızın kaynak kodlarını kamuya açık (açık kaynak) paylaşmanız gerekir**.
- **Ticari Satın Alma:** Kaynak kodunuzu gizli tutmak istiyorsanız, Ultralytics firmasından yıllık binlerce dolarlık ticari kurumsal lisans satın almanız gerekmektedir.

### 1.4. Güvenli ve Ücretsiz Ticari Çözüm Önerimiz
1. **Bayrak ile Kapatılabilir Olma (`ENABLE_CAR_PRECHECK=false`):**  
   Sistem varsayılan olarak bu kontrolü bayrakla devre dışı bırakılabilir şekilde tasarlanmıştır. Sunucunuz hızlı açılır, harici kütüphane bağımlılığı minimumda kalır.
2. **Lazy Loading (Gecikmeli Yükleme):**  
   Yapay zeka modeli backend ilk başladığında RAM'i şişirmez; sadece araç tespiti istendiğinde ilk kez belleğe yüklenir.
3. **Ticari Lisans Uyumlu Model (Öneri):**  
   İleride araç tespiti açılacaksa, Apache 2.0 veya MIT lisanslı COCO veri setiyle eğitilmiş Hugging Face / TensorFlow Hub MobileNet sınıflandırıcıları kullanılmalıdır. Bu modeller ticari kullanıma tamamen serbesttir ve kodunuzu açma zorunluluğu getirmez.

---

## 2. Depolama Servisi (`storage.py`) ve GLB / Küçük Resim Uyumu

### 2.1. Mevcut Durum
- Eski kodda `storage.py` boş bırakılmış, dosyalar doğrudan `upload_image_router.py` içerisinde `open("uploads/...", "wb")` şeklinde Windows/Linux diskine yazılmıştır.
- FastAPI `StaticFiles` eklentisi ile `http://localhost:8000/uploads/...` üzerinden sunulmaktadır.

### 2.2. GLB ve Küçük Resimler (Thumbnails) İçin Uygun mu?
- **GLB Dosyaları:** 3D modeller (.glb) ikili (binary) büyük dosyalardır (genellikle 5 MB - 50 MB). FastAPI statik dosya sunucusu yerel geliştirme için bu dosyaları istemciye (Flutter) sunmakta son derece başarılı ve yeterlidir.
- **MIME Tipi Uyumu:** `main.py` içinde `mimetypes.add_type("model/gltf-binary", ".glb")` tanımlanmıştır. Bu sayede Flutter 3D görüntüleyici motorları modeli doğru formatta indirir.
- **Hedef Mimari:**  
  `storage.py` içerisinde `LocalStorageService` adında merkezi bir servis kurulacaktır. Bu servis:
  1. Yüklenen ham fotoğrafları,
  2. Pillow ile üretilen 400x400 küçük önizleme resimlerini (thumbnails),
  3. Tripo API'den indirilecek nihai `.glb` 3D model dosyalarını  
  güvenli, benzersiz dosya adlarıyla (UUID) `uploads/` dizinine kaydedecek ve istemcinin erişeceği URL yolunu üretecektir. İleride AWS S3 veya Cloudflare R2'ye geçilmek istendiğinde sadece bu servis güncellenecektir; router kodlarına dokunulmayacaktır.

---

## 3. Tripo 3D İş Yönetimi Varsayımları (`generation_jobs`)
- Tripo API asenkron çalışır (Görev başlatılır, `task_id` alınır, arka planda durum sorgulanır ve tamamlanınca GLB indirilir).
- Çift kredi çekimini önlemek adına veritabanı seviyesinde `(scan_id, status IN ('pending', 'running'))` üzerinde benzersizlik kısıtı (Unique Constraint) olacaktır.
