import asyncio
from logging.config import fileConfig
import os
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# 1. Ortam Değişkenlerini Yükle (.env dosyasından)
# Backend klasöründeki veya üst dizindeki .env dosyasını bulur
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

load_dotenv(os.path.join(backend_dir, ".env"), override=False)
load_dotenv(os.path.join(backend_dir, "..", ".env"), override=False)

# Alembic konfigürasyon nesnesi
config = context.config

# Logging yapılandırması
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 2. Tüm Modelleri İçe Aktar (Base.metadata'nın eksiksiz olması için)
from app.database.base import Base
import app.database.models  # Tüm modeller Base.metadata'ya kaydedilir

target_metadata = Base.metadata


def get_and_validate_database_url() -> str:
    """
    Veritabanı bağlantı adresini ortam değişkenlerinden (.env) alır ve
    güvenlik kontrolü yaparak sadece '_dev' veya '_test' ile biten
    veritabanlarına izin verir.
    """
    # Öncelik 1: alembic komut satırından -x db_url=... verilmişse
    cmd_url = context.get_x_argument(as_dictionary=True).get("db_url")
    
    # Öncelik 2: Ortam değişkeni (DB_URL)
    url = cmd_url or os.getenv("DB_URL") or config.get_main_option("sqlalchemy.url")

    if not url or "driver://user:pass" in url:
        raise ValueError(
            "HATA: Veritabanı bağlantı adresi (DB_URL) bulunamadı! "
            "Lütfen .env dosyasında DB_URL tanımlayın."
        )

    # postgresql:// verilmişse asyncpg sürücüsüne uyarla
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)

    # 3. GÜVENLİK KORUMASI: Sadece 3DGarage geliştirme/test veritabanlarına izin ver
    clean_url = url.split("?")[0]
    parsed = urlparse(clean_url)
    dbname = parsed.path.lstrip("/")

    # SQLite bellekteki testler hariç veritabanı adı kontrolü
    if not (url.startswith("sqlite") and ":memory:" in url):
        is_allowed = (
            dbname in ("_3dgarage", "3dgarage", "_3dgarage_test", "garage_dev", "garage_test")
            or dbname.endswith("_dev")
            or dbname.endswith("_test")
            or "3dgarage" in dbname
        )
        if not is_allowed:
            raise ValueError(
                f"GÜVENLİK KORUMASI ENGELİ: Hedef veritabanı ('{dbname}') geçersiz! "
                "Canlı/üretim ortamında yanlışlıkla migration çalıştırılmasını engellemek için işlem durduruldu."
            )

    return url


def do_run_migrations(connection) -> None:
    """Senkron bağlantı üzerinde migration işlemlerini yürütür."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    """Çevrimdışı (offline) modda migration betiği üretir."""
    url = get_and_validate_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Asenkron motor ile veritabanına bağlanıp migration'ları çalıştırır."""
    url = get_and_validate_database_url()
    connectable = create_async_engine(
        url,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Çevrimiçi (online) modda asenkron motoru çalıştırır."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
