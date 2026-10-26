import os
import json
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, update, text
from sqlalchemy.pool import NullPool
from io import BytesIO
from urllib.parse import urlparse

# ── 1. GÜVENLİK KORUMASI VE TEST VERİTABANI BAĞLANTISI ──
# Testler sadece '_test' ile biten gerçek PostgreSQL veritabanında çalıştırılabilir
TEST_DB_URL = os.getenv("TEST_DB_URL", "postgresql+asyncpg://postgres:1234@localhost:5432/_3dgarage_test")

parsed = urlparse(TEST_DB_URL.split("?")[0])
dbname = parsed.path.lstrip("/")
if not dbname.endswith("_test"):
    raise ValueError(
        f"GÜVENLİK KORUMASI ENGELİ: Test veritabanı adı ('{dbname}') mutlaka '_test' ile bitmelidir! "
        f"Geliştirme veya üretim veritabanında test çalıştırılması engellendi."
    )

os.environ["DB_URL"] = TEST_DB_URL
os.environ["MY_TOKEN"] = "test_secret_key_12345678901234567890"
os.environ["TRIPO_API_KEY"] = "mock_tripo_key"
os.environ["ENABLE_CAR_PRECHECK"] = "false"
os.environ["DISABLE_BACKGROUND_TASKS"] = "true"

from app.database.models import User, UserStats, Scans
from app.core.security import create_access_token, get_password_hash
from app.core.config import calculate_scan_credits
from app.services.tripo_service import TripoService
from app.main import app
from app.database.db import get_session

# PostgreSQL Asenkron Test Motoru (NullPool ile her bağlantı bağımsız yönetilir)
test_engine = create_async_engine(TEST_DB_URL, poolclass=NullPool, echo=False)
TestSessionLocal = async_sessionmaker(bind=test_engine, expire_on_commit=False)


async def override_get_session():
    async with TestSessionLocal() as session:
        yield session

app.dependency_overrides[get_session] = override_get_session


@pytest.fixture(autouse=True)
def report_db_engine(request):
    """Her test çalıştığında kullanılan veritabanı motorunu ve veritabanı adını raporlar."""
    driver_name = test_engine.dialect.driver or "asyncpg"
    print(f"\n[TEST ÇALIŞIYOR: {request.node.name}] Motor: {test_engine.name} ({driver_name}) | DB: {dbname}")


@pytest_asyncio.fixture
async def db_session():
    """
    Şema Alembic migration tarafından kurulmuştur (create_all kullanılmaz).
    Her testten önce ve sonra tablolar CASCADE ile temizlenerek izolasyon sağlanır.
    """
    async with test_engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE TABLE users, scans, user_stats, modifications, scan_images, "
            "processed_2d, processed_3d, comments, likes, comment_likes CASCADE;"
        ))
    yield
    async with test_engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE TABLE users, scans, user_stats, modifications, scan_images, "
            "processed_2d, processed_3d, comments, likes, comment_likes CASCADE;"
        ))


# ── TEST 1: KREDİ HESAPLAMA DOĞRULAMASI ──
def test_credit_cost_calculation():
    # 2D modu her zaman sabit 15 kredi
    assert calculate_scan_credits("2d", "single", {}) == 15
    assert calculate_scan_credits("2d", "multiview", {"texture_quality": "extreme"}) == 15

    # 3D tek fotoğraf temel maliyet: 30 (modifikasyonsuz)
    assert calculate_scan_credits("3d", "single", {}, has_modifications=False) == 30

    # 3D tek fotoğraf modifikasyonlu: 30 base + 15 2d edit = 45
    assert calculate_scan_credits("3d", "single", {}, has_modifications=True) == 45

    # 3D tek fotoğraf + detailed texture (+15) + detailed geometry (+15) + pbr (+10) (modifikasyonsuz) = 70
    opts = {
        "texture_quality": "detailed",
        "geometry_quality": "detailed",
        "pbr": True
    }
    assert calculate_scan_credits("3d", "single", opts, has_modifications=False) == 70

    # 3D çoklu fotoğraf temel maliyet: 60 (modifikasyonsuz)
    assert calculate_scan_credits("3d", "multiview", {}, has_modifications=False) == 60

    # 3D çoklu fotoğraf + extreme texture (+25) + detailed geometry (+15) (modifikasyonsuz) = 100
    opts_multi = {
        "texture_quality": "extreme",
        "geometry_quality": "detailed",
        "pbr": False
    }
    assert calculate_scan_credits("3d", "multiview", opts_multi, has_modifications=False) == 100


# ── TEST 2: TEK PROMPT ŞABLONU VE İNGİLİZCE FORMAT DOĞRULAMASI ──
def test_build_modification_prompt():
    service = TripoService()

    # Yalnızca renk seçildiğinde
    prompt1 = service.build_modification_prompt(body_color="#FF0000")
    assert "Edit the car in image[1]" in prompt1
    assert "Change the exterior body paint color to #FF0000" in prompt1
    assert "rim model" not in prompt1
    assert "rear spoiler" not in prompt1
    assert "unchanged" in prompt1

    # Renk + Jant + Rüzgarlık seçildiğinde TEK promptta birleşmeli
    prompt_all = service.build_modification_prompt(
        body_color="glossy black",
        has_rims=True,
        rim_index=2,
        has_spoiler=True,
        spoiler_index=3
    )
    assert "image[1]" in prompt_all
    assert "Change the exterior body paint color to glossy black" in prompt_all
    assert "image[2]" in prompt_all
    assert "image[3]" in prompt_all


# ── TEST 3: KESİN YASAKLI TRIPO PARAMETRELERİ TESTİ ──
@pytest.mark.asyncio
async def test_tripo_forbidden_parameters(monkeypatch):
    service = TripoService(api_key="mock_key")
    captured_payload = {}

    class MockResp:
        status_code = 200
        def json(self):
            return {"code": 0, "data": {"task_id": "mock_task_123"}}

    class MockHttpxClient:
        async def post(self, url, headers=None, json=None, files=None):
            nonlocal captured_payload
            captured_payload = json
            return MockResp()

    async def mock_get_client(self):
        return MockHttpxClient()

    monkeypatch.setattr(TripoService, "get_client", mock_get_client)
    service.is_mock = False

    await service.image_to_model(
        image_input="test_token",
        options={
            "quad": True,
            "export_orientation": "align_image",
            "generate_parts": True,
            "smart_low_poly": True,
            "texture_quality": "standard",
            "geometry_quality": "standard",
            "pbr": True,
            "face_limit": 30000,
            "enable_image_autofix": False
        }
    )

    # KESİN KURALLAR KONTROLÜ:
    # 1. quad asla true olmamalı ve payload'da yer almamalı (FBX zorlamasını engellemek için)
    assert "quad" not in captured_payload or captured_payload["quad"] is not True
    # 2. export_orientation gönderilmemeli
    assert "export_orientation" not in captured_payload
    # 3. generate_parts gönderilmemeli
    assert "generate_parts" not in captured_payload
    # 4. smart_low_poly gönderilmemeli
    assert "smart_low_poly" not in captured_payload


# ── TEST 4: 2D MODÜLÜ PREPARE VE KREDİ DÜŞÜMÜ (15 KREDİ) ──
@pytest.mark.asyncio
async def test_prepare_scan_2d_mode(monkeypatch, db_session):
    async def mock_i2i(*args, **kwargs):
        return "mock_i2i_task_2d"

    monkeypatch.setattr("app.api.routers.upload_image_router.tripo_service.image_to_image", mock_i2i)

    async with TestSessionLocal() as session:
        user = User(
            name="Ahmet",
            surname="Yilmaz",
            email="ahmet@example.com",
            password=get_password_hash("pass123456")
        )
        session.add(user)
        await session.flush()
        stats = UserStats(user_id=user.user_id, user_credi=50)
        session.add(stats)
        await session.commit()
        user_id = user.user_id

    token = create_access_token({"sub": str(user_id)})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        dummy_file = ("car.jpg", BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"), "image/jpeg")
        response = await ac.post(
            "/scans/prepare",
            headers={"Authorization": f"Bearer {token}"},
            data={
                "car_name": "BMW M3",
                "mode": "2d",
                "method": "single",
                "modifications_json": json.dumps({"color_hex": "#00FF00"})
            },
            files={"files": dummy_file}
        )

    assert response.status_code == 201
    data = response.json()
    assert data["mode"] == "2d"
    assert data["credits_consumed"] == 15
    assert data["edit_task_id"] == "mock_i2i_task_2d"

    async with TestSessionLocal() as session:
        res = await session.execute(select(UserStats).where(UserStats.user_id == user_id))
        updated_stats = res.scalar_one()
        assert updated_stats.user_credi == 35


# ── TEST 5: 3D MODÜLÜ, 2D ÖNİZLEME SONRASI CONFIRM_3D VE IDEMPOTENCY (POSTGRESQL ROW LOCK) ──
@pytest.mark.asyncio
async def test_confirm_3d_workflow_and_idempotency(monkeypatch, db_session):
    async def mock_i2i(*args, **kwargs):
        return "mock_i2i_task_3d"
    async def mock_i2m(*args, **kwargs):
        return "mock_i2m_task_3d"

    monkeypatch.setattr("app.api.routers.upload_image_router.tripo_service.image_to_image", mock_i2i)
    monkeypatch.setattr("app.api.routers.upload_image_router.tripo_service.image_to_model", mock_i2m)

    async with TestSessionLocal() as session:
        user = User(
            name="Mehmet",
            surname="Demir",
            email="mehmet@example.com",
            password=get_password_hash("pass123456")
        )
        session.add(user)
        await session.flush()
        stats = UserStats(user_id=user.user_id, user_credi=100)
        session.add(stats)
        await session.commit()
        user_id = user.user_id

    token = create_access_token({"sub": str(user_id)})
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        dummy_file = ("car.jpg", BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"), "image/jpeg")
        prep_res = await ac.post(
            "/scans/prepare",
            headers={"Authorization": f"Bearer {token}"},
            data={
                "car_name": "Porsche 911",
                "mode": "3d",
                "method": "single",
                "options_json": json.dumps({"texture_quality": "detailed", "geometry_quality": "detailed", "pbr": True}),
                "modifications_json": json.dumps({"color_hex": "#FFFF00"})
            },
            files={"files": dummy_file}
        )

        assert prep_res.status_code == 201
        scan_id = prep_res.json()["scan_id"]

        # İlk aşamada 2D edit için 15 kredi düşüldü: 100 - 15 = 85
        async with TestSessionLocal() as session:
            res = await session.execute(select(UserStats).where(UserStats.user_id == user_id))
            assert res.scalar_one().user_credi == 85

            # Simüle: 2D edit tamamlandı ve durum awaiting_confirmation oldu
            await session.execute(
                update(Scans).where(Scans.scan_id == scan_id).values(status="awaiting_confirmation")
            )
            await session.commit()

        # confirm_3d gerçek PostgreSQL üzerinde SELECT ... FOR UPDATE (satır kilidi) çalıştırır
        confirm_res = await ac.post(
            f"/scans/{scan_id}/confirm_3d",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert confirm_res.status_code == 200
        confirm_data = confirm_res.json()
        assert confirm_data["status"] == "generating_3d"
        assert confirm_data["credits_consumed"] > 15

        # Idempotency: Çift tıklama / mükerrer çağrı 400 veya 409 dönmeli
        duplicate_res = await ac.post(
            f"/scans/{scan_id}/confirm_3d",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert duplicate_res.status_code in (400, 409)


# ── TEST 6: YETERSİZ KREDİ DURUMUNDA 402 DÖNÜLMESİ VE KREDİ GÜVENLİĞİ ──
@pytest.mark.asyncio
async def test_insufficient_credits_returns_402(db_session):
    async with TestSessionLocal() as session:
        user = User(
            name="Zeynep",
            surname="Kaya",
            email="zeynep@example.com",
            password=get_password_hash("pass123456")
        )
        session.add(user)
        await session.flush()
        stats = UserStats(user_id=user.user_id, user_credi=5)
        session.add(stats)
        await session.commit()
        user_id = user.user_id

    token = create_access_token({"sub": str(user_id)})
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        dummy_file = ("car.jpg", BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"), "image/jpeg")
        res = await ac.post(
            "/scans/prepare",
            headers={"Authorization": f"Bearer {token}"},
            data={
                "car_name": "Audi RS6",
                "mode": "2d",
                "method": "single"
            },
            files={"files": dummy_file}
        )

        assert res.status_code == 402
        assert "Yetersiz kredi" in res.json()["detail"]

    async with TestSessionLocal() as session:
        res = await session.execute(select(UserStats).where(UserStats.user_id == user_id))
        assert res.scalar_one().user_credi == 5


# ── TEST 7: BAŞARISIZ GÖREVDE OTOMATİK KREDİ İADESİ VE TEKRAR KUYRUĞA ALMAMA ──
@pytest.mark.asyncio
async def test_tripo_failure_atomic_refund(monkeypatch, db_session):
    async with TestSessionLocal() as session:
        user = User(
            name="Can",
            surname="Oz",
            email="can@example.com",
            password=get_password_hash("pass123456")
        )
        session.add(user)
        await session.flush()
        stats = UserStats(user_id=user.user_id, user_credi=50)
        session.add(stats)
        await session.commit()
        user_id = user.user_id

    token = create_access_token({"sub": str(user_id)})
    transport = ASGITransport(app=app)

    async def mock_i2i(*args, **kwargs):
        return "mock_failed_task"

    monkeypatch.setattr("app.api.routers.upload_image_router.tripo_service.image_to_image", mock_i2i)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        dummy_file = ("car.jpg", BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"), "image/jpeg")
        prep_res = await ac.post(
            "/scans/prepare",
            headers={"Authorization": f"Bearer {token}"},
            data={"car_name": "Ford Mustang", "mode": "2d", "method": "single"},
            files={"files": dummy_file}
        )
        assert prep_res.status_code == 201
        scan_id = prep_res.json()["scan_id"]

        async def mock_get_task(task_id):
            return {
                "task_id": task_id,
                "type": "image_to_image",
                "status": "failed",
                "progress": 10,
                "error_code": 2010,
                "error_message": "Tripo server error: insufficient system credits"
            }
        monkeypatch.setattr("app.api.routers.upload_image_router.tripo_service.get_task", mock_get_task)

        get_res = await ac.get(
            f"/scans/{scan_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert get_res.status_code == 200
        scan_data = get_res.json()
        assert scan_data["status"] == "failed"
        assert scan_data["credits_consumed"] == 0

    async with TestSessionLocal() as session:
        res = await session.execute(select(UserStats).where(UserStats.user_id == user_id))
        assert res.scalar_one().user_credi == 50
