"""
car_detection.py — CNN Araç Tespit Servisi
MobileNetV2 tabanlı eğitilmiş model ile araç tespiti yapar.
Stanford Cars veri setiyle eğitilmiş araba_modeli_guclu_v2.keras kullanır.
"""

import os
import numpy as np
from PIL import Image
import io
import logging

log = logging.getLogger("car_detection")

# ── Lazy-loaded model ──
_model = None
_class_names = None

MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "CNN_Otonom_Arac_Tespiti", "araba_modeli_guclu_v2.keras"
)
META_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "CNN_Otonom_Arac_Tespiti", "car_devkit", "devkit", "cars_meta.mat"
)


def _load_model():
    """Model ve sınıf isimlerini lazy-load et."""
    global _model, _class_names

    if _model is not None:
        return

    log.info("CNN araç tespit modeli yükleniyor...")

    # TensorFlow'u sadece gerektiğinde import et (bellek tasarrufu)
    import tensorflow as tf
    _model = tf.keras.models.load_model(os.path.normpath(MODEL_PATH))
    log.info(f"Model yüklendi: {MODEL_PATH}")

    # Sınıf isimlerini yükle
    try:
        from scipy.io import loadmat
        meta = loadmat(os.path.normpath(META_PATH))
        _class_names = [name[0] for name in meta['class_names'][0]]
        log.info(f"{len(_class_names)} sınıf ismi yüklendi.")
    except Exception as e:
        log.warning(f"Sınıf isimleri yüklenemedi: {e}")
        _class_names = []


def detect_car(image_bytes: bytes) -> dict:
    """
    Gelen fotoğrafta araç olup olmadığını tespit eder.

    Returns:
        {
            "is_car": bool,
            "confidence": float (0-100),
            "predicted_class": str | None,
            "class_index": int
        }
    """
    _load_model()

    import tensorflow as tf

    # Görseli hazırla
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = img.resize((224, 224))
    img_array = np.array(img, dtype=np.float32) / 255.0
    img_array = np.expand_dims(img_array, axis=0)

    # Tahmin yap
    predictions = _model.predict(img_array, verbose=0)
    class_idx = int(np.argmax(predictions))
    confidence = float(np.max(predictions) * 100)

    # Sınıf ismi
    predicted_name = None
    if _class_names and class_idx < len(_class_names):
        predicted_name = _class_names[class_idx]

    # %15 üzeri güven = araç var (eğitim seviyesine göre kalibre edilmiş eşik değeri)
    is_car = confidence > 15.0

    return {
        "is_car": is_car,
        "confidence": round(confidence, 2),
        "predicted_class": predicted_name,
        "class_index": class_idx,
    }
