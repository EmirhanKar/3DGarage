import logging
import os
import uuid
import asyncio
from typing import Dict, Any, List, Optional
import httpx
from app.core.config import TRIPO_API_KEY, TRIPO_BASE_URL

logger = logging.getLogger(__name__)

# Tripo v3 Hata Kodları Haritası
TRIPO_ERROR_MESSAGES = {
    1001: ("Geçersiz veya yetkisiz API anahtarı.", "Invalid or unauthorized API key."),
    1002: ("API anahtarının süresi dolmuş veya devre dışı.", "API key has expired or is disabled."),
    1004: ("Geçersiz istek parametreleri.", "Invalid request parameters."),
    1005: ("Desteklenmeyen dosya formatı veya bozuk dosya.", "Unsupported file format or corrupted file."),
    2001: ("Görev sırası dolu veya sistem meşgul.", "Task queue full or system busy."),
    2010: ("Tripo API hesap kredisi yetersiz.", "Insufficient Tripo API account credits."),
    2020: ("Görselde araba veya uygun nesne tespit edilemedi.", "Failed to detect suitable object/car in image."),
    3001: ("3D rekonstrüksiyon aşamasında hata oluştu.", "3D reconstruction step failed."),
    3002: ("Doku (texture) kaplama aşamasında hata oluştu.", "Texture generation step failed."),
}


class TripoAPIError(Exception):
    def __init__(self, code: int, message: str, raw_response: Optional[dict] = None):
        self.code = code
        self.message = message
        self.raw_response = raw_response
        self.user_friendly_tr, self.user_friendly_en = TRIPO_ERROR_MESSAGES.get(
            code,
            (f"Yapay zeka servisinde hata oluştu (Kod: {code}).", f"AI service error occurred (Code: {code}).")
        )
        super().__init__(f"TripoAPIError(code={code}, message={message})")


class TripoService:
    """
    Tripo 3D OpenAPI v3 İstemcisi.
    Tüm API çağrıları tek bir async HTTP istemcisi üzerinden zaman aşımı
    ve hata sınıflandırmasıyla yürütülür. API anahtarı asla loglanmaz.
    Geliştirme/test ortamında API anahtarı girilmediyse güvenli simülasyon modu sağlar.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or TRIPO_API_KEY
        self.base_url = (base_url or TRIPO_BASE_URL).rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None
        # Simülasyon modu kontrolü (anahtar yoksa, mock ile başlıyorsa veya TRIPO_MOCK_MODE aktifse)
        self.is_mock = (
            not self.api_key
            or self.api_key.startswith("BURAYA_")
            or self.api_key.startswith("mock")
            or self.api_key == "mock"
            or os.getenv("TRIPO_MOCK_MODE", "false").lower() == "true"
        )
        self._mock_tasks: Dict[str, Dict[str, Any]] = {}

    def _get_headers(self) -> Dict[str, str]:
        if not self.api_key and not self.is_mock:
            raise TripoAPIError(1001, "TRIPO_API_KEY ortam değişkeni ayarlanmamış!")
        return {
            "Authorization": f"Bearer {self.api_key}",
        }

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=30.0),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _handle_response(self, resp: httpx.Response) -> dict:
        try:
            data = resp.json()
        except Exception:
            raise TripoAPIError(resp.status_code, f"Beklenmeyen API yanıtı: {resp.text[:300]}")

        code = data.get("code", 0)
        if code != 0:
            msg = data.get("message") or data.get("msg") or "Bilinmeyen hata"
            logger.error("Tripo API Error returned: code=%s, msg=%s", code, msg)
            raise TripoAPIError(code=code, message=msg, raw_response=data)

        return data.get("data", {})

    # ── 1. Dosya Yükleme (POST /v3/files) ─────────────────────────────────────
    async def upload_file(self, file_bytes: bytes, filename: str = "image.jpg", content_type: str = "image/jpeg") -> str:
        """
        Yerel görseli Tripo sunucusuna yükler ve file_token döndürür.
        """
        if self.is_mock:
            token = f"file_mock_{uuid.uuid4().hex[:12]}"
            logger.info("[Tripo Mock] Uploaded file: %s -> %s", filename, token)
            return token

        client = await self.get_client()
        url = f"{self.base_url}/files"
        files = {"file": (filename, file_bytes, content_type)}
        headers = self._get_headers()

        logger.info("Uploading file to Tripo: %s (%d bytes)", filename, len(file_bytes))
        resp = await client.post(url, headers=headers, files=files)
        data = self._handle_response(resp)
        file_token = data.get("file_token") or data.get("token")
        if not file_token:
            raise TripoAPIError(1005, "Dosya yüklendi fakat file_token alınamadı.")
        return file_token

    # ── 2. 2D Modifikasyon / Düzenleme (POST /v3/generation/image-to-image) ────
    async def image_to_image(
        self,
        car_image: str,  # file_token veya public URL
        prompt: str,
        reference_images: Optional[List[str]] = None,
        model: str = "chat_image_2.5_sunburst"
    ) -> str:
        """
        Seçilen tüm modifikasyonları (renk, jant, rüzgarlık vb.) tek prompt ve tek istekte uygular.
        image[1] ana araç görseli, sonrakiler referans görsellerdir.
        """
        if self.is_mock:
            task_id = f"task_edit_{uuid.uuid4().hex[:12]}"
            self._mock_tasks[task_id] = {
                "task_id": task_id,
                "type": "image_to_image",
                "status": "success",
                "progress": 100,
                "output": {
                    "rendered_image_url": "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Models/master/2.0/Duck/screenshot/screenshot.png",
                    "image": "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Models/master/2.0/Duck/screenshot/screenshot.png"
                }
            }
            logger.info("[Tripo Mock] Created image-to-image task: %s", task_id)
            return task_id

        client = await self.get_client()
        url = f"{self.base_url}/generation/image-to-image"
        headers = self._get_headers()

        inputs = [car_image]
        if reference_images:
            inputs.extend(reference_images)

        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
        }

        if len(inputs) == 1:
            payload["input"] = inputs[0]
        else:
            payload["inputs"] = inputs
            payload["input"] = inputs[0]

        logger.info("Starting Tripo image-to-image with model=%s, input_count=%d", model, len(inputs))
        resp = await client.post(url, headers=headers, json=payload)
        data = self._handle_response(resp)
        task_id = data.get("task_id")
        if not task_id:
            raise TripoAPIError(1004, "Görev başlatılamadı, task_id dönmedi.")
        return task_id

    # ── 3. 3D Model Üretimi - Tek Görsel (POST /v3/generation/image-to-model) ─
    async def image_to_model(
        self,
        image_input: str,  # file_token, public URL veya önceki edit task_id'si
        options: Optional[Dict[str, Any]] = None,
        model: str = "v3.1-20260211"
    ) -> str:
        """
        2D düzenlenmiş görselden 3D GLB model üretir.
        """
        if self.is_mock:
            task_id = f"task_model_{uuid.uuid4().hex[:12]}"
            self._mock_tasks[task_id] = {
                "task_id": task_id,
                "type": "image_to_model",
                "status": "success",
                "progress": 100,
                "output": {
                    "model_url": "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Models/master/2.0/Duck/glTF-Binary/Duck.glb",
                    "model": "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Models/master/2.0/Duck/glTF-Binary/Duck.glb",
                    "rendered_image_url": "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Models/master/2.0/Duck/screenshot/screenshot.png"
                }
            }
            logger.info("[Tripo Mock] Created image-to-model task: %s", task_id)
            return task_id

        client = await self.get_client()
        url = f"{self.base_url}/generation/image-to-model"
        headers = self._get_headers()
        options = options or {}

        payload: Dict[str, Any] = {
            "model": options.get("model", model),
            "input": image_input,
        }

        texture_q = options.get("texture_quality", "standard")
        if texture_q in ("standard", "detailed", "extreme"):
            payload["texture_quality"] = texture_q

        geometry_q = options.get("geometry_quality", "standard")
        if geometry_q in ("standard", "detailed"):
            payload["geometry_quality"] = geometry_q

        if "pbr" in options:
            payload["pbr"] = bool(options["pbr"])

        face_limit = options.get("face_limit", 35000)
        if isinstance(face_limit, int) and 5000 <= face_limit <= 100000:
            payload["face_limit"] = face_limit

        if "enable_image_autofix" in options:
            payload["enable_image_autofix"] = bool(options["enable_image_autofix"])

        orientation = options.get("orientation")
        if orientation in ("default", "align_image"):
            payload["orientation"] = orientation

        # Güvenlik kuralları (kesinlikle çıkarılır):
        payload.pop("quad", None)
        payload.pop("export_orientation", None)
        payload.pop("generate_parts", None)
        payload.pop("smart_low_poly", None)

        logger.info("Starting Tripo image-to-model with input=%s, texture=%s", image_input, texture_q)
        resp = await client.post(url, headers=headers, json=payload)
        data = self._handle_response(resp)
        task_id = data.get("task_id")
        if not task_id:
            raise TripoAPIError(1004, "3D üretim görevi başlatılamadı, task_id dönmedi.")
        return task_id

    # ── 4. 3D Model Üretimi - Çoklu Görsel (POST /v3/generation/multiview-to-model)
    async def multiview_to_model(
        self,
        views: List[Dict[str, str]],  # [{"front": token/url}, {"left": ...}, ...]
        options: Optional[Dict[str, Any]] = None,
        model: str = "v3.1-20260211"
    ) -> str:
        """
        Çoklu açıdan (front, left, back, right) 3D GLB model üretir.
        """
        if self.is_mock:
            task_id = f"task_multi_{uuid.uuid4().hex[:12]}"
            self._mock_tasks[task_id] = {
                "task_id": task_id,
                "type": "multiview_to_model",
                "status": "success",
                "progress": 100,
                "output": {
                    "model_url": "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Models/master/2.0/Duck/glTF-Binary/Duck.glb",
                    "model": "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Models/master/2.0/Duck/glTF-Binary/Duck.glb",
                    "rendered_image_url": "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Models/master/2.0/Duck/screenshot/screenshot.png"
                }
            }
            logger.info("[Tripo Mock] Created multiview-to-model task: %s", task_id)
            return task_id

        client = await self.get_client()
        url = f"{self.base_url}/generation/multiview-to-model"
        headers = self._get_headers()
        options = options or {}

        payload: Dict[str, Any] = {
            "model": options.get("model", model),
            "inputs": views,
        }

        texture_q = options.get("texture_quality", "standard")
        if texture_q in ("standard", "detailed", "extreme"):
            payload["texture_quality"] = texture_q

        geometry_q = options.get("geometry_quality", "standard")
        if geometry_q in ("standard", "detailed"):
            payload["geometry_quality"] = geometry_q

        if "pbr" in options:
            payload["pbr"] = bool(options["pbr"])

        face_limit = options.get("face_limit", 40000)
        if isinstance(face_limit, int) and 5000 <= face_limit <= 100000:
            payload["face_limit"] = face_limit

        resp = await client.post(url, headers=headers, json=payload)
        data = self._handle_response(resp)
        task_id = data.get("task_id")
        if not task_id:
            raise TripoAPIError(1004, "Multiview 3D üretim görevi başlatılamadı.")
        return task_id

    # ── 5. Görev Sorgulama (GET /v3/tasks/{task_id}) ──────────────────────────
    async def get_task(self, task_id: str) -> dict:
        """
        Görev durumunu ve çıktı linklerini (model_url, rendered_image_url) sorgular.
        """
        if self.is_mock and task_id in self._mock_tasks:
            return self._mock_tasks[task_id]

        client = await self.get_client()
        url = f"{self.base_url}/tasks/{task_id}"
        headers = self._get_headers()

        resp = await client.get(url, headers=headers)
        data = self._handle_response(resp)
        return data

    # ── 6. Dosya İndirme ──────────────────────────────────────────────────────
    async def download_file(self, url: str) -> bytes:
        """
        Tripo tarafından üretilen GLB model veya önizleme görselini indirir.
        """
        if self.is_mock and ("Duck.glb" in url or "screenshot.png" in url):
            # 1x1 şeffaf png veya basit ikili veri
            return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"

        client = await self.get_client()
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content

    # ── Prompt Oluşturucu Yardımcı Metot ─────────────────────────────────────
    @staticmethod
    def build_modification_prompt(
        body_color: Optional[str] = None,
        has_rims: bool = False,
        rim_index: int = 2,
        has_spoiler: bool = False,
        spoiler_index: int = 3,
        extra_prompt: Optional[str] = None
    ) -> str:
        """
        Tripo 2D Image-to-Image için İngilizce modifikasyon prompt'u üretir.
        """
        instructions = ["Edit the car in image[1]."]

        if body_color:
            clean_color = body_color.strip()
            instructions.append(f"Change the exterior body paint color to {clean_color}.")

        if has_rims:
            instructions.append(f"Replace all car wheels and rims with the rim model shown in image[{rim_index}].")

        if has_spoiler:
            instructions.append(f"Install the rear spoiler wing shown in image[{spoiler_index}] securely on the trunk.")

        if extra_prompt:
            instructions.append(extra_prompt.strip())

        instructions.append(
            "Keep the car's body geometry, perspective, camera angle, shadows, reflections, "
            "background, lighting, license plate, and all other unmodified parts completely unchanged."
        )

        return " ".join(instructions)


# Global Singleton TripoService
tripo_service = TripoService()
