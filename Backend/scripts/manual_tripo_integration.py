"""
3DGarage Tripo v3 Canli Entegrasyon Scripti
============================================
Bu script gercek Tripo API v3 uclarini test eder.
DIKKAT: Gercek Tripo kredisi harcar!
Calistirma:
    python scripts/manual_tripo_integration.py --live --image path/to/car.jpg
"""

import os
import sys
import asyncio
import argparse
import logging

# Set python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.tripo_service import TripoService, TripoAPIError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TripoLiveTest")


async def main():
    parser = argparse.ArgumentParser(description="Tripo API v3 Entegrasyon Dogrulama Scripti")
    parser.add_argument("--live", action="store_true", help="Gercek API uclarini cagir ve kredi harca")
    parser.add_argument("--image", type=str, default=None, help="Test araba gorseli dosya yolu (JPEG/PNG)")
    parser.add_argument("--color", type=str, default="#FF0000", help="Modifikasyon govde rengi (HEX)")
    args = parser.parse_args()

    api_key = os.getenv("TRIPO_API_KEY")
    if not api_key or api_key.startswith("BURAYA_"):
        logger.error("HATA: TRIPO_API_KEY ortam degiskeni (.env) icinde tanimli degil!")
        sys.exit(1)

    if not args.live:
        print("\n" + "=" * 60)
        print("UYARI: Script guvenli DRY-RUN modunda calisiyor.")
        print("Gercek Tripo gorevi baslatmak ve kredi harcamak icin '--live' bayragini ekleyin:")
        print("  python scripts/manual_tripo_integration.py --live --image car.jpg")
        print("=" * 60 + "\n")
        return

    service = TripoService(api_key=api_key)
    service.is_mock = False

    logger.info("1. Tripo API Baglantisi dogrulaniyor (Base URL: %s)...", service.base_url)

    if not args.image or not os.path.exists(args.image):
        logger.error("Gecerli bir test gorseli belirtilmedi! '--image <dosya_yolu>' parametresini verin.")
        sys.exit(1)

    with open(args.image, "rb") as f:
        img_bytes = f.read()

    # 1. Dosya Yukleme
    logger.info("2. Test gorseli yukleniyor (%d bytes)...", len(img_bytes))
    file_token = await service.upload_file(img_bytes, filename=os.path.basename(args.image))
    logger.info("-> Dosya yuklendi, file_token: %s", file_token)

    # 2. 2D Modifikasyon
    prompt = service.build_modification_prompt(body_color=args.color)
    logger.info("3. 2D Image-to-Image gorevi baslatiliyor (Prompt: %s)...", prompt)
    edit_task_id = await service.image_to_image(
        car_image=file_token,
        prompt=prompt,
        model="chat_image_2.5_sunburst"
    )
    logger.info("-> 2D Edit Task baslatildi: %s", edit_task_id)

    # 3. Polling
    logger.info("4. Gorev durumu sorgulaniyor (polling)...")
    for _ in range(30):
        await asyncio.sleep(5)
        task_data = await service.get_task(edit_task_id)
        status = task_data.get("status")
        progress = task_data.get("progress", 0)
        logger.info("-> Task Durumu: %s (%%%s)", status, progress)

        if status == "success":
            output = task_data.get("output", {})
            img_url = output.get("rendered_image_url") or output.get("image")
            logger.info("TEBRIKLER! 2D Duzenleme basarili: %s", img_url)
            break
        elif status in ("failed", "cancelled"):
            logger.error("Gorev basarisiz oldu: %s", task_data)
            break

    await service.close()


if __name__ == "__main__":
    asyncio.run(main())
