# 🏎️ 3DGarage - Yapay Zeka Destekli Araç Modifikasyon ve 3D Modelleme Stüdyosu

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Flutter](https://img.shields.io/badge/Frontend-Flutter%203.x-02569B.svg?style=flat&logo=flutter)](https://flutter.dev)
[![Python](https://img.shields.io/badge/Python-3.14-3776AB.svg?style=flat&logo=python)](https://python.org)
[![Tripo 3D](https://img.shields.io/badge/AI%20Engine-Tripo%20API%20v3-FF6F00.svg?style=flat)](https://developers.tripo3d.com)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg?style=flat)]()
[![Tests](https://img.shields.io/badge/Tests-7%2F7%20Passed-brightgreen.svg?style=flat)]()

**3DGarage**, kullanıcıların gerçek araç fotoğrafları üzerinde yapay zeka ile **2D fotogerçekçi modifikasyon** (gövde boyası, jant değişimi, rüzgarlık/spoiler ekleme) uygulamasını ve onaylanan tasarım üzerinden yüksek kaliteli **3D GLB modelleri** üretmesini sağlayan uçtan uca hibrit bir mobil & sunucu platformudur.

---

## 📋 İçindekiler
- [Temel Özellikler](#-temel-özellikler)
- [Mimari ve Teknoloji Yığını](#-mimari-ve-teknoloji-yığını)
- [Klasör Mimarisi](#-klasör-mimarisi)
- [Kullanıcı Akışı ve Çalışma Prensibi](#-kullanıcı-akışı-ve-çalışma-prensibi)
- [Tripo API v3 Entegrasyon Mimarisi](#-tripo-api-v3-entegrasyon-mimarisi)
- [Kredi Güvenliği ve Atomik Düşüm](#-kredi-güvenliği-ve-atomik-düşüm)
- [API Uç Noktaları ve Kullanım](#-api-uç-noktaları-ve-kullanım)
- [Veritabanı ve Alembic Migration](#-veritabanı-ve-alembic-migration)
- [Kurulum ve Çalıştırma Rehberi](#-kurulum-ve-çalıştırma-rehberi)
- [Test ve Doğrulama](#-test-ve-doğrulama)
- [Ortam Değişkenleri (.env)](#-ortam-değişkenleri-env)
- [Bilinen Sınırlamalar ve Yol Haritası](#-bilinen-sınırlamalar-ve-yol-haritası)

---

## 🚀 Temel Özellikler

### 1. 2D Modifikasyon Hattı (Image-to-Image)
- **Tek Prompt Şablonu:** Gövde rengi (HEX), jant modeli ve arka spoiler parçalarını tek bir İngilizce komut ve referans parça görselleri (`image[1..3]`) ile işler.
- **Sunburst 2.5 Modeli:** Tripo `chat_image_2.5_sunburst` motoru sayesinde modifiye edilmeyen kaporta, arka plan, ışık ve kamera açısı %100'e yakın korunur.

### 2. 3D Model Rekonstrüksiyon Hattı (Image-to-Model & Multiview)
- **Ön-Onaylı 3D Üretimi:** 3D modeli doğrudan ham fotoğraftan üretmek yerine, kullanıcının beğendiği 2D modifiye görsel üzerinden üretir.
- **Tek ve Çoklu Açı Desteği:** Tek fotoğraftan hızlı 3D modelleme veya 4 kanonik açıdan (`front`, `back`, `left`, `right`) yüksek tutarlılıklı modelleme.
- **Kişiselleştirilebilir Kalite:** Doku (Standard / Detailed / Extreme 8K), Geometri (Standard / Detailed) ve PBR materyal desteği.
- **İnteraktif GLB Görüntüleyici:** Mobil arayüzde `model_viewer_plus` ile 360 derece döndürme, yakınlaştırma ve ortam aydınlatması.

### 3. Kullanıcı Deneyimi ve Akıllı Donanım Entegrasyonu
- **Şablonlu Kamera ve Canlı Su Terazisi:** Sensörler (`sensors_plus`) yardımıyla jiroskop destekli optimum araç çekim açısı yönlendirmesi.
- **MobileNet Araç Ön Kontrolü:** Fotoğrafta araba tespit edilmezse yapay zeka API'sine istek gönderilmez; kullanıcı kredisi sıfır riskle korunur.
- **Render Sırasında Mini Oyun:** Render ve yapay zeka üretimi beklenirken kullanıcıya araba yarışı ve mini oyunlar sunulur.
- **Global Render Bildirim Çubuğu:** Kullanıcı uygulamada gezinirken arka plandaki üretimin canlı yüzdesini gösterir.
- **İki Dilli Lokalizasyon:** Türkçe ve İngilizce dil desteği (`sistem_ve_dil.dart`).

---

## 🛠️ Mimari ve Teknoloji Yığını

```mermaid
graph TD
    A["Flutter Mobil İstemci"] -->|"HTTPS / Multipart Form"| B["FastAPI Backend (app/main.py)"]
    B --> C["MobileNet Pre-Check"]
    B --> D["PostgreSQL / SQLite (Async SQLAlchemy 2)"]
    B --> E["LocalStorageService (app/services/storage.py)"]
    B -->|"Async HTTP (httpx)"| F["Tripo API v3 (openapi.tripo3d.com/v3)"]
    F -->|"image-to-image"| G["2D Önizleme"]
    F -->|"image-to-model"| H["3D GLB Model"]
    H -->|"Download & Save"| E
```

### Backend
- **Framework:** FastAPI ≥ 0.110.0
- **Çalışma Zamanı:** Python 3.14 (AsyncIO)
- **ORM / Veritabanı:** SQLAlchemy 2.0 (Async) + asyncpg (PostgreSQL) / aiosqlite (Test)
- **Veritabanı Yönetimi:** Alembic Migrations
- **HTTP İstemcisi:** httpx ≥ 0.27.0
- **Güvenlik:** JWT (PyJWT) + Passlib (Bcrypt) + Row-level locking (`with_for_update`)
- **Görüntü İşleme & Yapay Zeka:** Pillow, TFLite (MobileNet v2), NumPy

### Frontend
- **Framework:** Flutter SDK ≥ 3.11.1
- **3D Render:** `model_viewer_plus` ≥ 1.10.0 (WebGL / Google `<model-viewer>`)
- **Kamera & Sensör:** `camera` ≥ 0.11.0, `sensors_plus` ≥ 6.1.1
- **Durum Yönetimi:** `render_state.dart` (ChangeNotifier / Singleton Polling Manager)
- **Ağ:** `http` ≥ 1.6.0, `mime` ≥ 2.0.0
- **Kalıcı Hafıza:** `shared_preferences` ≥ 2.3.0

---

## 📁 Klasör Mimarisi

```
D:\3DGarage\
├── Backend\
│   ├── alembic\
│   │   ├── versions\
│   │   │   └── 20261026_01_add_tripo_v3_fields_to_scans.py  # Tripo v3 DB migrasyonu
│   │   └── env.py
│   ├── app\
│   │   ├── api\
│   │   │   ├── deps.py                                      # JWT auth & API key kontrolü
│   │   │   └── routers\
│   │   │       ├── upload_image_router.py                   # /prepare, /confirm_3d, /retry_edit, /garage
│   │   │       ├── modification_router.py                   # Taslak ve modifikasyon yönetimi
│   │   │       ├── user_router.py                           # Kullanıcı auth, profil, bakiye
│   │   │       ├── plugins_router.py                        # Jant ve renk katalog listeleri
│   │   │       ├── community_router.py                      # Paylaşımlar, beğeniler, yorumlar
│   │   │       └── store_router.py                          # Parça mağazası
│   │   ├── core\
│   │   │   ├── config.py                                    # Kredi hesaplama, Tripo konfigürasyonu
│   │   │   └── security.py                                  # Bcrypt hash & JWT üretimi
│   │   ├── database\
│   │   │   ├── models\                                      # Scans, User, UserStats, Modification...
│   │   │   ├── schemas\                                     # ScanResponse, Processed3DInfo...
│   │   │   ├── crud\                                        # DB operasyonları
│   │   │   └── db.py                                        # Async engine & sessionmaker
│   │   ├── services\
│   │   │   ├── tripo_service.py                             # Tripo API v3 async istemcisi
│   │   │   ├── storage.py                                   # Kalıcı yerel GLB / thumbnail saklama
│   │   │   └── car_detection.py                             # Yerel araç ön kontrol filtresi
│   │   └── main.py                                          # FastAPI app, CORS, Lifespan tasks
│   ├── scripts\
│   │   └── manual_tripo_integration.py                      # Canlı Tripo v3 test scripti
│   ├── tests\
│   │   └── test_tripo_workflow.py                           # 7 adet birim & entegrasyon testi
│   ├── uploads\catalog\                                     # Sunucu tarafı jant & spoiler katalog PNG'leri
│   ├── .env.example                                         # Örnek çevre değişkenleri
│   ├── alembic.ini
│   ├── pytest.ini
│   └── requirements.txt
│
├── Frontend\
│   ├── assets\
│   │   ├── jantlar\                                         # Katalog jant şeffaf PNG'leri
│   │   ├── spoilers\                                        # Katalog spoiler şeffaf PNG'leri
│   │   └── onboarding\                                      # Karşılama ekranı görselleri
│   ├── lib\
│   │   ├── main.dart                                        # Flutter main()
│   │   ├── config.dart                                      # Backend API base URL
│   │   ├── sistem_ve_dil.dart                               # TR/EN sözlük ve çeviri motoru
│   │   ├── render_state.dart                                # Arka plan polling ve durum yöneticisi
│   │   ├── global_render_banner.dart                        # Üretim durumunu gösteren global banner
│   │   ├── oyun_sayfasi.dart                                # Mini yarış oyunu ve render ekranı
│   │   ├── sayfalar_islem.dart                              # Mod seçimi, fotoğraf yükleme, modifikasyon
│   │   ├── modeller\
│   │   │   ├── scan_model.dart                              # Scan JSON serileştirme
│   │   │   └── kullanici_model.dart                         # Kullanıcı bakiye modeli
│   │   ├── sayfalar\
│   │   │   ├── onizleme_onay_sayfasi.dart                   # 2D önizleme, onay ve tekrar deneme
│   │   │   ├── model_3d_viewer.dart                         # GLB 3D etkileşimli görüntüleyici
│   │   │   ├── sablonlu_kamera.dart                         # Kamera arayüzü
│   │   │   └── canli_su_terazisi.dart                       # Jiroskop seviye göstergesi
│   │   └── servisler\
│   │       ├── api_servisi.dart                             # Backend HTTP istemcisi
│   │       └── auth_servisi.dart                            # Oturum ve token yönetimi
│   ├── pubspec.yaml
│   └── analysis_options.yaml
│
├── docs\                                                    # Tasarım kararları ve varsayımlar
├── .gitignore
├── README.md
└── 3DGarage_Proje_Durum_Raporu.pdf                          # Resmi proje durum raporu
```

---

## 🔄 Kullanıcı Akışı ve Çalışma Prensibi

```mermaid
sequenceDiagram
    autonumber
    actor User as Kullanıcı (Mobil)
    participant UI as Flutter Arayüzü
    participant API as FastAPI Backend
    participant Tripo as Tripo API v3
    participant DB as PostgreSQL DB

    User->>UI: Fotoğraf çeker ve modifikasyonları seçer (Renk, Jant, Spoiler)
    UI->>API: POST /scans/prepare (Multipart)
    API->>API: MobileNet ile araç varlığı doğrulanır
    API->>DB: Atomik satır kilidi ile ilk 15 kredi düşülür
    API->>Tripo: POST /v3/files (Araç + Parça referansları)
    API->>Tripo: POST /v3/generation/image-to-image (Tek prompt)
    API-->>UI: 201 Created (status: pending_edit, task_id)
    
    loop Polling (Her 3-5 saniye)
        UI->>API: GET /scans/{id}
        API->>Tripo: GET /v3/tasks/{task_id}
    end
    
    Tripo-->>API: 2D Edit Success (rendered_image_url)
    API->>API: Görseli sunucuya indir (uploads/images_2d)
    API-->>UI: status: awaiting_confirmation (Önizleme hazır)
    
    alt 2D Modu İse
        UI->>User: Modifiye görseli gösterir ve akış tamamlanır.
    else 3D Modu İse
        User->>UI: "Beğendim, 3D Model Üret" butonuna tıklar
        UI->>API: POST /scans/{id}/confirm_3d
        API->>DB: Kalan 3D kredisini (ör. 55 cr) atomik düşer
        API->>Tripo: POST /v3/generation/image-to-model
        API-->>UI: status: generating_3d
        
        loop Polling (Render Bekleme + Mini Oyun)
            UI->>API: GET /scans/{id}
            API->>Tripo: GET /v3/tasks/{task_id}
        end
        
        Tripo-->>API: 3D Model Success (model_url GLB)
        API->>API: GLB dosyasını sunucuya kaydet (models_3d)
        API-->>UI: status: done (model_url hazır)
        UI->>User: Model3DViewer ekranını açar (Etkileşimli 3D Görünüm)
    end
```

---

## 🌐 Tripo API v3 Entegrasyon Mimarisi

### Kullanılan Uç Noktalar
| İşlem | Tripo Endpoint | HTTP | Açıklama |
| :--- | :--- | :--- | :--- |
| **Dosya Yükleme** | `/v3/files` | POST | Araç ve katalog parçası yükleme (`file_token`) |
| **2D Modifikasyon** | `/v3/generation/image-to-image` | POST | Tek istekte parça giydirme (`chat_image_2.5_sunburst`) |
| **3D Rekonstrüksiyon (Tek)** | `/v3/generation/image-to-model` | POST | Onaylanan 2D görselden GLB model üretimi |
| **3D Rekonstrüksiyon (Çoklu)** | `/v3/generation/multiview-to-model` | POST | Kanonik açılardan tutarlı GLB üretimi |
| **Görev Sorgulama** | `/v3/tasks/{task_id}` | GET | Durum sorgulama (`queued`, `running`, `success`, `failed`) |

### Tekil Prompt Şablonu
Tüm seçilen modifikasyonlar **tek bir İngilizce prompt** içinde birleştirilir. Ardışık düzenlemeler görüntüde açı ve kalite kayması yaratacağından engellenmiştir:
```text
Edit the car in image[1]. Change the exterior body paint color to #00E5FF. Replace the wheels with the rim model shown in image[2]. Add the rear spoiler shown in image[3] on the trunk. Keep the car's shape, camera angle, background, lighting and all other parts unchanged.
```
- `image[1]`: Kullanıcının yüklediği araç fotoğrafı
- `image[2]`: Seçilen katalog jantı referansı (seçilmediyse prompta girmez)
- `image[3]`: Seçilen katalog spoiler referansı (seçilmediyse prompta girmez)

### ⛔ Kesin Yasaklı Tripo Parametreleri
Mobil tarafta `model_viewer_plus` (WebGL/Three.js) kullanıldığı için aşağıdaki parametreler `TripoService` katmanında kesin olarak filtrelenir:
- `quad=true`: **ASLA GÖNDERİLMEZ** (Çıktıyı FBX formatına zorlar, GLB formatını bozar).
- `export_orientation`: **ASLA GÖNDERİLMEZ** (Sessiz eksen yön kaymalarına yol açar).
- `generate_parts`: **ASLA GÖNDERİLMEZ** (PBR ve doku haritaları ile uyumsuzdur).
- `smart_low_poly`: **ASLA GÖNDERİLMEZ** (Öngörülemeyen kalite kaybı yaratır).

---

## 💰 Kredi Güvenliği ve Atomik Düşüm

Sistem, kullanıcının bakiye güvenliğini sağlamak için çok katmanlı savunma uygular:

1. **Satır Kilidi (`SELECT ... FOR UPDATE`):** Eşzamanlı isteklerde race condition oluşması engellenir.
2. **İki Aşamalı Kredi Düşümü:**
   - Fotoğraf yüklendiğinde yalnızca 2D önizleme ücreti (**15 Kredi**) tahsil edilir.
   - 3D üretim bedeli, kullanıcı üretilen 2D sonucu görüp **"Beğendim, 3D Üret"** butonuna basana kadar düşülmez.
3. **Otomatik İade Garantisi:** Tripo görevi herhangi bir sebeple başarısız olursa (`status: failed`), harcanan kredi derhal kullanıcı hesabına **eksiksiz iade edilir**.
4. **Yeniden Kuyruğa Almama Kuralı:** Başarısız olan görevler otomatik olarak tekrar denenip kullanıcının kredisini tüketmez; sadece kullanıcının açık isteğiyle (`/retry_edit`) tekrarlanır.
5. **Idempotency Kilidi:** `is_locked` bayrağı ile aynı tarama için çift tıklama veya paralel isteklerle mükerrer harcama yapılması önlenir (HTTP 409).

### Kredi Fiyatlandırma Matrisi
| İşlem | Kredi | Açıklama |
| :--- | :--- | :--- |
| **2D Modifikasyon (Tüm Seçimler)** | 15 Kredi | Renk + Jant + Rüzgarlık dahil sabit ücret |
| **3D Single-View (Temel)** | 30 Kredi | Standart doku + standart geometri |
| **3D Multi-View (Temel)** | 60 Kredi | En az 2 açıdan rekonstrüksiyon |
| **Detailed Texture** | +15 Kredi | Yüksek çözünürlüklü doku kaplama |
| **Extreme Texture (8K)** | +25 Kredi | 8K Ultra doku kaplama |
| **Detailed Geometry** | +15 Kredi | Yüksek poligon geometrik yoğunluk |
| **PBR Aydınlatma** | +10 Kredi | Fiziksel tabanlı materyal yansıması |

---

## 🔌 API Uç Noktaları ve Kullanım

### 1. POST `/scans/prepare`
Kullanıcı fotoğrafını, işlem modunu (2D/3D), kalite seçeneklerini ve modifikasyonları alarak süreci başlatır.

**İstek (Multipart/Form-Data):**
```http
POST /scans/prepare HTTP/1.1
Authorization: Bearer <JWT_TOKEN>
Content-Type: multipart/form-data; boundary=boundary

--boundary
Content-Disposition: form-data; name="car_name"

Porsche 911 GT3
--boundary
Content-Disposition: form-data; name="mode"

3d
--boundary
Content-Disposition: form-data; name="method"

single
--boundary
Content-Disposition: form-data; name="options_json"

{"texture_quality": "detailed", "geometry_quality": "detailed", "pbr": true, "face_limit": 30000}
--boundary
Content-Disposition: form-data; name="modifications_json"

{"color_hex": "#FFFF00", "rim_name": "bbs_rs", "spoiler_id": "spoiler_gt"}
--boundary
Content-Disposition: form-data; name="files"; filename="car.jpg"
Content-Type: image/jpeg

<binary jpeg data>
--boundary--
```

**Başarılı Yanıt (201 Created):**
```json
{
  "scan_id": 142,
  "car_name": "Porsche 911 GT3",
  "mode": "3d",
  "method": "single",
  "status": "pending_edit",
  "credits_estimated": 70,
  "credits_consumed": 15,
  "edit_task_id": "task_edit_982bfbca23",
  "progress": 25,
  "progress_stage": "2D modifikasyon yapay zekası çalışıyor..."
}
```

---

### 2. GET `/scans/{scan_id}`
Tarama kaydının durumunu döner. Tripo görevi devam ediyorsa backend otomatik olarak sorgular ve dosyalar hazır olduğunda yerel depoya indirip yanıtı günceller.

**Başarılı Yanıt (2D Önizleme Hazır - 200 OK):**
```json
{
  "scan_id": 142,
  "mode": "3d",
  "status": "awaiting_confirmation",
  "image_url": "uploads/images_2d/scan_142/edit_fa8319.png",
  "thumbnail_url": "uploads/thumbnails/12/thumb_edit_142.jpg",
  "credits_consumed": 15,
  "progress": 50,
  "progress_stage": "2D önizleme hazır. Onayınız bekleniyor."
}
```

---

### 3. POST `/scans/{scan_id}/confirm_3d`
Kullanıcı üretilen 2D sonucu beğendiğinde kalan 3D modelleme kredisi tahsil edilerek 3D rekonstrüksiyon başlatılır.

**Başarılı Yanıt (200 OK):**
```json
{
  "scan_id": 142,
  "status": "generating_3d",
  "model_task_id": "task_model_33a829f0",
  "credits_consumed": 70,
  "progress": 75,
  "progress_stage": "3D model rekonstrüksiyonu başladı..."
}
```

---

### 4. POST `/scans/{scan_id}/retry_edit`
Kullanıcı önizlemeyi beğenmediğinde yeni parametrelerle 2D düzenlemeyi yineler.

---

## 🗄️ Veritabanı ve Alembic Migration

Alembic migrasyon dosyası: [`Backend/alembic/versions/20261026_01_add_tripo_v3_fields_to_scans.py`](file:///d:/3DGarage/Backend/alembic/versions/20261026_01_add_tripo_v3_fields_to_scans.py)

`scans` tablosuna eklenen yeni alanlar:
- `mode` (VARCHAR(10)): `'2d'` veya `'3d'`
- `options_json` (TEXT): Seçilen doku, poligon ve PBR parametreleri
- `modifications_json` (TEXT): Seçilen renk, jant ve rüzgarlık bilgileri
- `edit_task_id` (VARCHAR(64)): Tripo 2D Image-to-Image görev UUID'si
- `model_task_id` (VARCHAR(64)): Tripo 3D Image-to-Model görev UUID'si
- `credits_estimated` (INTEGER): Hesaplanan toplam kredi
- `credits_consumed` (INTEGER): Fiilen harcanan bakiye
- `is_locked` (BOOLEAN): Eşzamanlı mükerrer çağrı engelleme kilidi
- `progress_percent` (INTEGER): Yüzdesel ilerleme
- `progress_stage` (VARCHAR(100)): Kullanıcıya gösterilen aşama mesajı
- `error_code` / `error_hint`: Tripo hata kodu ve anlaşılır kullanıcı mesajı

---

## 💻 Kurulum ve Çalıştırma Rehberi

### Gereksinimler
- Python 3.11+ (Tercihen 3.14)
- Flutter SDK 3.11+
- PostgreSQL 14+ (veya testler için dahili SQLite)

### 1. Backend Kurulumu
```bash
cd D:\3DGarage\Backend

# Sanal ortam oluşturma ve etkinleştirme
python -m venv venv
.\venv\Scripts\activate   # Windows

# Bağımlılıkları yükleme
pip install -r requirements.txt

# Çevre değişkenlerini ayarlama
cp .env.example .env
# .env dosyasını açıp DB_URL ve TRIPO_API_KEY değerlerini düzenleyin

# Veritabanı migrasyonlarını uygulama
alembic upgrade head

# Sunucuyu başlatma
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Swagger Dokümantasyonu: `http://localhost:8000/docs`

### 2. Frontend Kurulumu
```bash
cd D:\3DGarage\Frontend

# Paket bağımlılıklarını alma
flutter pub get

# Statik kod analizi (0 hata)
flutter analyze --no-fatal-infos --no-fatal-warnings

# Testleri çalıştırma
flutter test

# Cihazda veya emülatörde çalıştırma
flutter run
```

---

## 🧪 Test ve Doğrulama

### 1. Otomatik Backend Birim Testleri
Backend dizininde 7 kapsamlı test senaryosu bulunmaktadır:
```bash
cd D:\3DGarage\Backend
pytest -v
```

**Test Kapsamı ve Sonuçları:**
1. `test_credit_cost_calculation` ✅ – 2D/3D tüm modifikasyon ve kalite permütasyonlarının kredi hesabı doğrulanır.
2. `test_build_modification_prompt` ✅ – Tekil İngilizce prompt ve `image[1..3]` parça dizilimleri doğrulanır.
3. `test_tripo_forbidden_parameters` ✅ – `quad`, `export_orientation`, `generate_parts` ve `smart_low_poly` parametrelerinin engellendiği doğrulanır.
4. `test_prepare_scan_2d_mode` ✅ – 2D hazırlık akışı ve 15 kredi düşümü doğrulanır.
5. `test_confirm_3d_workflow_and_idempotency` ✅ – 3D onay süreci ve çift istek engeli (HTTP 409) test edilir.
6. `test_insufficient_credits_returns_402` ✅ – Yetersiz bakiyede HTTP 402 dönülerek bakiye kaybı engellenir.
7. `test_tripo_failure_atomic_refund` ✅ – Başarısız yapay zeka görevinde anında atomik kredi iadesi test edilir.

### 2. Manuel Canlı Entegrasyon Scripti
Gerçek API kredisi kullanarak canlı Tripo API v3 uç noktalarını test etmek için geliştirilmiş script:
```bash
# Güvenli mod (DRY-RUN - Kredi harcamaz):
python Backend/scripts/manual_tripo_integration.py

# Canlı API Modu (DİKKAT: Gerçek Tripo kredisi harcar):
python Backend/scripts/manual_tripo_integration.py --live --image test_car.jpg --color "#FF0000"
```

---

## 🔐 Ortam Değişkenleri (.env)

| Değişken | Varsayılan / Örnek | Açıklama |
| :--- | :--- | :--- |
| `DB_URL` | `postgresql+asyncpg://user:pass@localhost:5432/3dgarage` | Veritabanı bağlantı dizesi |
| `MY_TOKEN` | `secret_jwt_key_here` | JWT imzalama anahtarı |
| `ADMIN_API_KEY` | `admin_secret_key` | Yönetici uç noktaları erişim anahtarı |
| `TRIPO_API_KEY` | `tsk_live_...` | Tripo 3D OpenAPI anahtarı |
| `TRIPO_BASE_URL` | `https://openapi.tripo3d.com/v3` | Tripo API Base URL |
| `TRIPO_WEBHOOK_SECRET` | `secret_webhook_key` | Tripo webhook doğrulama gizli anahtarı |
| `ENABLE_CAR_PRECHECK` | `true` | MobileNet araç ön kontrolünü açar/kapatır |
| `DISABLE_BACKGROUND_TASKS`| `false` | Periyodik arka plan görevlerini kapatır |

---

## 📌 Bilinen Sınırlamalar ve Yol Haritası

- [ ] **Açı Yönlendirmesi (Spoiler):** Doğrudan önden çekilen fotoğraflarda arka spoiler model tarafından net algılanamayabilir. Kullanıcı arayüzünde "Arka 3/4 Açı Önerisi" uyarısı aktif durumdadır.
- [ ] **Webhook Prodüksiyon Dağıtımı:** Geliştirme ortamında %100 kararlılık için polling mekanizması kullanılmaktadır. Prodüksiyonda webhook rotası entegre edilebilir.
- [ ] **3D Baskı Dışa Aktarma:** GLB modellerinin STL formatına dönüştürülerek 3D yazıcı çıktısına hazırlanması planlanmaktadır.

---

## 📄 Lisans
Bu proje özel mülkiyete tabi olup tüm hakları saklıdır. İzin alınmaksızın çoğaltılamaz veya dağıtılamaz.
