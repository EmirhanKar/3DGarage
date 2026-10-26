# MODIF-AI Backend Temizlik ve Kullanım Haritası (Usage Map)

> **Belge Amacı:** Bu doküman, backend içerisindeki tüm router'lar, uç noktalar (endpoints), veritabanı tabloları, şemalar, CRUD fonksiyonları ve servislerin ayrıntılı kullanım haritasını ve temizlik kararlarını içerir.  
> **Temel Kural:** Flutter mobil uygulamasının (`D:\MODIFIAI\Frontend`) kullandığı hiçbir özellik veya uç nokta silinmeyecek; eski yerel 3D servis işçisine (worker) ait artık mekanizmalar temizlenecektir.

---

## 1. Flutter Uygulaması Konum Tespiti
- **Workspace İçi Durum:** Flutter kodu `D:\modifi_ai` (yeni workspace) içerisinde bulunmamaktadır.
- **Harici Konum Tespiti:** Sistemde yapılan taramada eski ve aktif mobil istemci kod tabanının **`D:\MODIFIAI\Frontend`** dizininde yer aldığı tespit edilmiştir.
- **İnceleme Yöntemi:** Mobil uygulamanın `lib/servisler/api_servisi.dart`, `lib/config.dart` ve ilgili ekran dosyalarındaki tüm ağ çağrıları satır satır incelenerek kanıtlar listelenmiştir.

---

## 2. Router ve Uç Noktalar (Endpoints) Kullanım Haritası

### 2.1. `user_router.py` (Prefix: `/users`)
| Endpoint | HTTP | Flutter Çağrısı (Dosya:Satır) | Dahili Backend Kullanımı | Karar | Gerekçe / Açıklama |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/register` | POST | `api_servisi.dart:57` (`kayitOl`) | - | **KEEP** | Yeni kullanıcı kaydı ve 100 hoş geldin kredisi atama. |
| `/login` | POST | `api_servisi.dart:86` (`girisYap`) | `main.py:132, 179` (OAuth2 URL) | **KEEP** | JWT erişim jetonu (token) üretimi. |
| `/me` | GET | `api_servisi.dart:112` (`beniBilgileriniGetir`) | - | **KEEP** | Kullanıcı profil ve kredi/istatistik bilgisi. |
| `/me` | PATCH | `api_servisi.dart:141` (`profilGuncelle`) | - | **KEEP** | İsim, soyisim, şifre güncelleme. |
| `/me/upload-photo` | POST | `api_servisi.dart:159` (`profilFotoYukle`) | - | **KEEP** | Profil fotoğrafı yükleme ve JPEG formatlama. |
| `/me` | DELETE | `api_servisi.dart:571` (`hesapSil`) | - | **KEEP** | KVKK/GDPR uyumlu hesap ve ilişkili tüm verileri silme. |
| `/game/score` | POST | `api_servisi.dart:644` (`oyunSkoruKaydet`) | - | **KEEP** | Mini oyun skorlarını (araba yarışı, uçan kuş) kaydetme. |
| `/game/leaderboard`| GET | `api_servisi.dart:630` (`oyunLiderlikTablosuGetir`) | - | **KEEP** | Haftalık oyun liderlik tablosu (ilk 3 kullanıcı). |

---

### 2.2. `upload_image_router.py` (Prefix: `/scans`)
| Endpoint | HTTP | Flutter Çağrısı (Dosya:Satır) | Dahili Backend Kullanımı | Karar | Gerekçe / Açıklama |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/upload_image` | POST | `api_servisi.dart:190` (`fotografYukle`) | `scanCreate`, `scanImageCreate` | **KEEP** | Fotoğraf yükleme, kredi düşme ve tarama başlatma ana noktası. |
| `/garage` | GET | `api_servisi.dart:223` (`garajiGetir`) | `get_user_scans` | **KEEP** | Kullanıcının tamamlanmış taramalarını listeler. |
| `/{scan_id}` | GET | `api_servisi.dart:237` (`scanDetayGetir`) | `build_scan_response` | **KEEP** | Araç detay, model URL ve modifikasyon durumu sorgulama. |
| `/{scan_id}` | DELETE| `api_servisi.dart:250` (`scanSil`) | Cascade scan silme | **KEEP** | Kullanıcının aracını silmesi. |
| `/detect_car` | POST | `api_servisi.dart:263` (`aracTespitEt`) | `car_detection.py` | **KEEP** | Fotoğrafta araç olup olmadığını teyit eden opsiyonel ön kontrol. |
| `/garage/{scan_id}`| GET | Çağrılmıyor (Yinelenen uç nokta) | - | **REMOVE** | Flutter doğrudan `GET /scans/{scan_id}` çağırıyor. Gereksiz çift rota. |
| `/pending_3d` | GET | Çağrılmıyor (Sadece eski 3D servisi) | - | **REMOVE** | Eski yerel worker kuyruk sorgulama noktası. Tripo API ile doğrudan sunucu entegre olacağı için gerek kalmadı. |
| `/claim_3d/{scan_id}`| POST| Çağrılmıyor (Sadece eski 3D servisi) | `PROCESSING_LEASE_SECONDS` | **REMOVE** | Eski işçi kiralama (lease) ve atomik claim token mekanizması. |
| `/progress/{scan_id}`| POST| Çağrılmıyor (Sadece eski 3D servisi) | `ProgressRequest` | **REMOVE** | Eski işçinin aşama bildirdiği heartbeat mekanizması. |
| `/fail/{scan_id}` | POST| Çağrılmıyor (Sadece eski 3D servisi) | `FailRequest` | **REMOVE** | Eski işçi hata bildirim mekanizması. |
| `/complete/3d/{scan_id}`| POST/PUT| Çağrılmıyor (Sadece eski 3D servisi)| Raw binary GLB yazımı | **REMOVE** | Eski işçinin binary GLB yükleme noktası. Tripo'dan doğrudan arka plan görevi ile dosya çekilecek. |
| `/reset/{scan_id}` | POST| Çağrılmıyor | - | **REMOVE** | Eski işçi hatalarını sıfırlamak için yazılmış admin endpoint. Yeni yapıda generation_jobs üzerinden yönetilecek. |
| `/pending_2d` | GET | Çağrılmıyor | - | **REMOVE** | Eski 2D segmentasyon işçi sorgusu. |
| `/complete/2d/{scan_id}`| POST| Çağrılmıyor | - | **UNSURE** | 2D işlem tamamlandığında görsel yükleme noktası. Flutter çağırmıyor; admin/işçi için mi tutulmalı yoksa 2D de yeni API sağlayıcısına mı bağlanacak? *(Kullanıcıya soruldu)* |

---

### 2.3. `plugins_router.py` (Prefix: `/plugins`)
| Endpoint | HTTP | Flutter Çağrısı (Dosya:Satır) | Dahili Backend Kullanımı | Karar | Gerekçe / Açıklama |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/jants` | GET | `api_servisi.dart:286` (`jantlariGetir`) | - | **KEEP** | Kullanıcıya modifiye ekranında jant listesini sunar. |
| `/jants/{jant_id}` | GET | Çağrılmıyor | - | **KEEP** | Standart REST tekil jant okuma uç noktası. |
| `/jants` | POST | Çağrılmıyor (Admin panel / curl) | `JantCreate` | **KEEP** | Yeni jant ve 3D jant görseli ekleme (İçerik yönetimi için gerekli). |
| `/jants/{jant_id}` | DELETE | Çağrılmıyor (Admin panel / curl) | - | **KEEP** | Hatalı jant kaydını silme (İçerik yönetimi için gerekli). |
| `/colors` | GET | `api_servisi.dart:304` (`renkleriGetir`)| - | **KEEP** | Renk paleti seçeneklerini getirir. |
| `/colors/{color_id}`| GET | Çağrılmıyor | - | **KEEP** | Standart REST tekil renk okuma uç noktası. |
| `/colors` | POST | Çağrılmıyor (Admin panel / curl) | `ColorCreate` | **KEEP** | Yeni renk kodu (#HEX) ekleme. |
| `/colors/{color_id}`| DELETE | Çağrılmıyor (Admin panel / curl) | - | **KEEP** | Renk silme. |

---

### 2.4. `community_router.py` (Prefix: `/community`)
| Endpoint | HTTP | Flutter Çağrısı (Dosya:Satır) | Dahili Backend Kullanımı | Karar | Gerekçe / Açıklama |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/feed` | GET | `api_servisi.dart:322` (`feedGetir`) | Beğeni/yorum sayıları | **KEEP** | Keşfet sekmesinde paylaşılan araçları listeler. |
| `/explore/top` | GET | `api_servisi.dart:336` (`exploreTopGetir`)| Beğeniye göre sıralama | **KEEP** | En çok beğenilen ilk 5 aracı ana sayfada vitrine çıkarır. |
| `/{scan_id}/like` | POST | `api_servisi.dart:350` (`begeniToggle`) | `Like` tablosu | **KEEP** | Araç beğenme ve beğeniyi geri alma. |
| `/{scan_id}/comments` | GET | `api_servisi.dart:363` (`yorumlariGetir`)| `Comment` listesi | **KEEP** | Aracın yorumlarını listeler. |
| `/{scan_id}/comments` | POST | `api_servisi.dart:378` (`yorumEkle`)| `CommentCreate` | **KEEP** | Araca yorum ekleme. |
| `/comments/{comment_id}/like` | POST | `api_servisi.dart:394` (`yorumBegeniToggle`)| `CommentLike` tablosu | **KEEP** | Yorum beğenme. |
| `/comments/{comment_id}` | DELETE | `api_servisi.dart:407` (`yorumSil`) | - | **KEEP** | Kullanıcının kendi yorumunu silmesi. |
| `/{scan_id}/share` | POST | `api_servisi.dart:586` (`toplulugaPaylas`)| `Scans.is_shared = True` | **KEEP** | Aracı toplulukta keşfete açma. |
| `/{scan_id}/unshare` | POST | `api_servisi.dart:599` (`kesfettenKaldir`)| `Scans.is_shared = False`| **KEEP** | Aracı keşfetten gizleme. |

---

### 2.5. `store_router.py` (Prefix: `/store`)
| Endpoint | HTTP | Flutter Çağrısı (Dosya:Satır) | Dahili Backend Kullanımı | Karar | Gerekçe / Açıklama |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/packages` | GET | `api_servisi.dart:422` (`paketleriGetir`) | Sabit paket listesi | **KEEP** | Kredi paketleri ve abonelik seçeneklerini listeler. |
| `/purchase/{package_id}`| POST | `api_servisi.dart:436` (`paketSatinAl`)| `UserStats`, `Subscription` | **KEEP** | Paket satın alımı (kredi ve abonelik tanımlama). |
| `/my-credits` | GET | `api_servisi.dart:449` (`krediBilgisiGetir`)| Kredi ve kalan süre | **KEEP** | Kullanıcının anlık kredi ve üyelik seviyesi. |
| `/referral` | POST | `api_servisi.dart:616` (`davetPaylas`)| `User.referral_used = True`| **KEEP** | Arkadaşını davet eden kullanıcıya tek seferlik 50 kredi hediyesi. |

---

### 2.6. `modification_router.py` (Prefix: `/modifications`)
| Endpoint | HTTP | Flutter Çağrısı (Dosya:Satır) | Dahili Backend Kullanımı | Karar | Gerekçe / Açıklama |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/costs` | GET | `api_servisi.dart:466` (`modifikasyonKredileriGetir`) | Sabit maliyet tablosu | **KEEP** | Jant/renk başına kredi maliyetini döner (örn: jant: 30, renk: 20). |
| `/` (boş post) | POST | `api_servisi.dart:490` (`modifikasyonOlustur`) | `Modification`, `UserStats` | **KEEP** | Araca seçilen jant ve rengi uygular, kredi düşer. |
| `/{modification_id}`| PATCH | `api_servisi.dart:528` (`modifikasyonGuncelle`) | `ModificationUpdate` | **KEEP** | Mevcut modifikasyonu günceller (fark kredisi tahsil edilir). |
| `/drafts` | GET | `api_servisi.dart:552` (`taslaklariGetir`) | `Scans.status != 'completed'`| **KEEP** | Tamamlanmamış veya işlemdeki araç taslaklarını gösterir. |
| `/{scan_id}` | GET | Çağrılmıyor | - | **KEEP** | REST standardı olarak tekil scan'in modifikasyonunu getirme. |
| `/{modification_id}`| DELETE | Çağrılmıyor | - | **KEEP** | Modifikasyonu silme/iptal etme. |

---

### 2.7. `main.py` ve Arka Plan Görevleri
| Fonksiyon / Görev | Karar | Gerekçe / Açıklama |
| :--- | :--- | :--- |
| `GET /` (Root Endpoint) | **KEEP** | Sunucunun ayakta olup olmadığını kontrol eden sağlık kontrolü (health check). |
| `weekly_score_reset_task` | **KEEP** | Her 7 günde bir mini oyun skorlarını sıfırlayan arka plan görevi. |
| `dead_lease_watchdog_task` | **REMOVE** | Eski 3D worker'ın süresi dolmuş kiralarını (`DEAD_LEASE`) temizleyen saatlik görev. Tripo API ile bu mimariye gerek yoktur. |

---

## 3. Veritabanı Tabloları Kullanım Haritası

| Tablo Adı | Model Sınıfı | Sütunlar | İlişkiler (Foreign Keys) | Okuyan / Yazan Kodlar | Karar | Açıklama |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `users` | `User` | `user_id` (PK), `name`, `surname`, `profil_image_url`, `email`, `password`, `phone_number`, `is_admin`, `referral_used`, `game_score*` (6 adet oyun alanı) | Yok (Ana tablo) | `user_router`, `community_router`, `store_router`, `deps.py`, `main.py` | **KEEP** | Kullanıcı hesapları, profilleri ve oyun skorları. |
| `user_stats` | `UserStats` | `userstats_id` (PK), `user_id` (FK -> users, unique), `user_credi`, `create_image`, `render_image` | `users.user_id` | `user_router`, `upload_image_router`, `store_router`, `modification_router` | **KEEP** | Kredi bakiyesi ve işlem istatistikleri. |
| `subscriptions` | `Subscription` | `subscription_id` (PK), `user_id` (FK -> users), `tier`, `start_date`, `end_date` | `users.user_id` | `user_router`, `store_router` | **KEEP** | Kullanıcı abonelik (free/premium) bilgileri. |
| `scans` | `Scans` | `scan_id` (PK), `user_id` (FK -> users), `method`, `status`, `car_name`, `description`, `is_shared`, `created_at`<br><br>*(Eski Worker Alanları)*:<br>`status_updated_at`, `claimed_by`, `claim_token`, `retry_count`, `failed_step`, `error_code`, `error_detail`, `error_hint`, `progress_stage`, `progress_percent`, `next_attempt_at` | `users.user_id` | `upload_image_router`, `community_router`, `modification_router`, `scan_crud.py` | **KEEP (Alanları Temizle)** | Ana araç tarama tablosu. Eski 3D worker'a ait `claimed_by`, `claim_token`, `retry_count`, `failed_step`, `next_attempt_at`, `progress_stage`, `status_updated_at` sütunları silinecek; `status`, `progress`, `error_code`, `error_hint` korunacak. |
| `scan_images` | `ScanImage` | `scanimage_id` (PK), `scan_id` (FK -> scans), `modification_id` (FK -> modifications), `image_url` | `scans.scan_id`, `modifications.modification_id` | `upload_image_router`, `scan_image_crud.py` | **KEEP** | Kullanıcının yüklediği 1 veya 4 adet ham fotoğraflar. |
| `processed_3d` | `Processed3D` | `processed3d_id` (PK), `scan_id` (FK -> scans, unique), `model_url`, `thumbnail_url` | `scans.scan_id` | `upload_image_router`, `community_router`, `modification_router` | **KEEP (Genişletilecek)** | 3D model GLB ve görsel URL'lerini tutar. Step 3'te `scale_known`, `orientation_info`, `job_id` eklenecek. |
| `processed_2d` | `Processed2D` | `processed2d_id` (PK), `scan_id` (FK -> scans, unique), `image_url`, `thumbnail_url` | `scans.scan_id` | `upload_image_router`, `community_router` | **KEEP** | 2D işlem görmüş render/görsel URL'lerini tutar. |
| `modifications` | `Modification`| `modification_id` (PK), `scan_id` (FK -> scans), `user_id` (FK -> users), `color_id` (FK -> colors), `jant_id` (FK -> jant), `paint_location`, `last_step` | `scans.scan_id`, `users.user_id`, `colors.color_id`, `jant.jant_id` | `modification_router`, `upload_image_router`, `scan_crud.py` | **KEEP** | Araca uygulanan modifikasyon adımları. |
| `jant` | `Jant` | `jant_id` (PK), `model_name`, `category`, `image_url` | Yok (Modifications tarafından refere edilir) | `plugins_router`, `modification_router` | **KEEP** | Jant kataloğu. |
| `colors` | `Colors` | `color_id` (PK), `color_code` | Yok (Modifications tarafından refere edilir) | `plugins_router`, `modification_router` | **KEEP** | Renk paleti kataloğu. |
| `likes` | `Like` | `like_id` (PK), `user_id` (FK -> users), `scan_id` (FK -> scans) (Unique: user+scan) | `users.user_id`, `scans.scan_id` | `community_router` | **KEEP** | Araç beğenileri. |
| `comments` | `Comment` | `comment_id` (PK), `user_id` (FK -> users), `scan_id` (FK -> scans), `content`, `created_at` | `users.user_id`, `scans.scan_id` | `community_router` | **KEEP** | Araç yorumları. |
| `comment_likes` | `CommentLike` | `like_id` (PK), `user_id` (FK -> users), `comment_id` (FK -> comments) (Unique: user+comment) | `users.user_id`, `comments.comment_id` | `community_router` | **KEEP** | Yorum beğenileri. |

---

## 4. Pydantic Şemaları (Schemas) Kullanım Haritası

| Şema Sınıfı | Tanımlandığı Dosya | Kullanan Yerler | Karar | Gerekçe / Açıklama |
| :--- | :--- | :--- | :--- | :--- |
| `ScanBase`, `ScanCreate`, `ScanResponse` | `scan_schemas.py` | `upload_image_router`, `scan_crud` | **KEEP** | Mobil istemciye giden ana tarama yanıt modeli. |
| `ScanImageBrief`, `JantBrief`, `ColorBrief`, `ModificationBrief`, `Processed3DInfo`, `Processed2DInfo` | `scan_schemas.py` | `ScanResponse` içinde | **KEEP** | İlişkili verilerin JSON serileştirmesi için gereklidir. |
| `ClaimResponse` | `scan_schemas.py` | `upload_image_router.py:285` | **REMOVE** | Eski 3D worker kiralama yanıtı. |
| `ProgressRequest` | `scan_schemas.py` | `upload_image_router.py:354` | **REMOVE** | Eski 3D worker ilerleme isteği. |
| `FailRequest` | `scan_schemas.py` | `upload_image_router.py:390` | **REMOVE** | Eski 3D worker hata bildirimi isteği. |
| `UserCreate`, `UserResponse`, `UserLogin`, `UserToken`, `UserBase`, `UserUpdate` | `user_schemas.py` | `user_router`, `user_crud` | **KEEP** | Kullanıcı kimlik doğrulama ve profil şemaları. |
| `UserStatsBase`, `UserStatsCreate`, `UserStatsResponse`, `UserStatsUpdate` | `userstats_schemas.py` | `user_router`, `userstats_crud` | **KEEP** | Kredi ve istatistik şemaları. |
| `CommentCreate`, `CommentResponse`, `FeedItemResponse` | `community_schemas.py` | `community_router` | **KEEP** | Topluluk akışı ve yorum şemaları. |
| `JantResponse`, `ColorResponse`, `JantCreate`, `ColorCreate` | `plugins_schemas.py` | `plugins_router` | **KEEP** | Eklenti (jant/renk) şemaları. |
| `ScanImageBase`, `ScanImageCreate`, `ScanImageResponse` | `scan_image_schemas.py` | `scan_image_crud` | **KEEP** | Yüklenen fotoğrafların CRUD şemaları. |

---

## 5. CRUD Modülleri Kullanım Haritası

| CRUD Modülü | Fonksiyonlar | Kullanan Router / Servis | Karar | Gerekçe |
| :--- | :--- | :--- | :--- | :--- |
| `scan_crud.py` | `scanCreate`, `scanUpdate`, `scanRead`, `get_user_scans`, `get_scan_by_id` | `upload_image_router.py` | **KEEP** | Tarama oluşturma, durum güncelleme ve garaj listeleme işlemleri. |
| `scan_image_crud.py` | `scanImageCreate`, `scanImageUpdate`, `scanImageRead` | `upload_image_router.py` | **KEEP** | Fotoğraf yollarını DB'ye kaydetme. |
| `user_crud.py` | `UserCreate`, `UserUpdate`, `get_user_by_email` | `user_router.py` | **KEEP** | Kullanıcı CRUD işlemleri. |
| `userstats_crud.py` | `UserStatsCreate`, `update_user_stats` | `user_router.py` | **KEEP** | Kredi/istatistik CRUD işlemleri. |

---

## 6. Servisler (Services) Kullanım Haritası

| Servis Dosyası | Mevcut Durumu | Kullanıldığı Yer | Karar | Teknik İnceleme ve Açıklama |
| :--- | :--- | :--- | :--- | :--- |
| `car_detection.py` | MobileNetV2 (Stanford Cars) tabanlı Keras modeli (`araba_modeli_guclu_v2.keras`) | `upload_image_router.py:739` (`POST /scans/detect_car`), Flutter: `api_servisi.dart:263` | **KEEP (Opsiyonel & Lazy)** | Kullanıcı fotoğraf yüklediğinde fotoğrafta gerçekten araç olup olmadığını tespit eder. Tripo API'ye boşuna kredi harcamamak için mükemmel bir koruma katmanıdır. `ENABLE_CAR_PRECHECK=false` yapılarak varsayılan olarak devre dışı bırakılabilir; açıldığında ise model belleğe yalnızca ilk çağrıda yüklenir (lazy loading). Lisanslama detayı `docs/ASSUMPTIONS.md` dosyasında açıklandı. |
| `storage.py` | **BOŞ DOSYA (0 Bayt)** | Kod içerisinde doğrudan çağrılmıyor; router'lar doğrudan `open()` ve `os.path.join()` kullanıyor. | **KEEP & REFACTOR** | Şu an yüklenen dosyalar doğrudan `uploads/` klasörüne `open()` ile yazılmaktadır. Bu dosya, GLB 3D modellerini, kullanıcı fotoğraflarını ve küçük resimleri (thumbnails) tek bir standart arayüzden yöneten temiz bir yerel depolama sınıfına (`LocalStorageService`) dönüştürülecektir. |

---

## 7. Açık Kalan / Kullanıcı Kararı Gerektiren Konular (UNSURE)
1. **`POST /scans/complete/2d/{scan_id}` ve `GET /scans/pending_2d`:**  
   Mobil uygulama bu uç noktaları çağırmıyor. Eski sistemde harici bir yapay zeka servisi 2D segmentasyon maskeleri/görselleri yüklüyordu. Tripo 3D geçişinde bu 2D uç noktalar tamamen kaldırılmalı mı, yoksa gelecekteki 2D entegrasyonu için şimdilik tutulmalı mı? (Önerimiz: Eski worker mimarisini temizlemek adına kaldırılması).
