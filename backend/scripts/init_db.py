import asyncio
import sys
from pathlib import Path

# Add backend root directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select, text
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import AsyncSessionLocal, async_engine
from app.models import Farm, Plot, Producer, User


async def init_database() -> None:
    """
    Initializes database extensions, creates all ORM tables, and seeds an initial admin user.
    """
    print("=" * 70)
    print("🚀 Iniciando inicialización de la Base de Datos CaféTrace SV...")
    print(f"📡 Conectando a: {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
    print("=" * 70)

    try:
        # 1. Enable required PostgreSQL extensions (UUID and PostGIS)
        print("\n📦 Paso 1: Habilitando extensiones de PostgreSQL (uuid-ossp, postgis)...")
        async with async_engine.begin() as conn:
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "postgis";'))
            print("   ✅ Extensiones 'uuid-ossp' y 'postgis' activadas con éxito.")

            # Query PostGIS version to verify spatial engine readiness
            pg_res = await conn.execute(text("SELECT PostGIS_Version();"))
            pg_ver = pg_res.scalar()
            print(f"   🗺️  PostGIS Versión detectada: {pg_ver}")

        # 2. Create all tables defined in SQLAlchemy 2.0 Base metadata
        print("\n📦 Paso 2: Creando tablas relacionales y espaciales...")
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            print("   ✅ Tablas creadas: users, producers, farms, plots.")

        # 3. Seed initial SuperAdmin user if none exists
        print("\n📦 Paso 3: Verificando usuario administrador inicial...")
        async with AsyncSessionLocal() as session:
            admin_email = "admin@cafetrace.sv"
            stmt = select(User).where(User.email == admin_email)
            result = await session.execute(stmt)
            existing_admin = result.scalar_one_or_none()

            if not existing_admin:
                admin_user = User(
                    email=admin_email,
                    hashed_password=get_password_hash("AdminCafeSV2026!"),
                    full_name="Administrador General CaféTrace",
                    role="ADMIN",
                    is_active=True,
                )
                session.add(admin_user)
                await session.commit()
                print(f"   ✅ Usuario Administrador creado exitosamente:")
                print(f"      - Email: {admin_email}")
                print(f"      - Contraseña: AdminCafeSV2026!")
                print(f"      - Rol: ADMIN")
            else:
                print(f"   ℹ️  El usuario administrador '{admin_email}' ya existe en el sistema.")

        print("\n" + "=" * 70)
        print("🎉 ¡Inicialización de Base de Datos completada exitosamente!")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ ERROR durante la inicialización de la base de datos: {e}", file=sys.stderr)
        raise
    finally:
        await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_database())
