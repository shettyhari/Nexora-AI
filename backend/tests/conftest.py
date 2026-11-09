import os
import sys
import asyncio
import pytest
import pytest_asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_FILE = "./test_nexora.db"
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_FILE}"

os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["SECRET_KEY"] = "test_secret_key_nexora_32_characters_long"

from app.core.database import Base, get_db
from app.core.rate_limiter import rate_limiter
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.preference import UserPreference
from app.models.profile import Profile
from app.models.user import User

test_engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False}
)

TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    rate_limiter.reset()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with TestAsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def test_user():
    async with TestAsyncSessionLocal() as session:
        user = User(
            id="user_test_1",
            email="test@nexora.ai",
            username="testuser",
            hashed_password=hash_password("MySecretPassword123"),
            is_active=True,
            is_verified=True,
            role="user",
        )
        session.add(user)
        profile = Profile(user_id=user.id, display_name="Test User")
        prefs = UserPreference(user_id=user.id, theme="dark", default_model="nexora-pro")
        session.add(profile)
        session.add(prefs)
        await session.commit()
        await session.refresh(user)
        return user


@pytest_asyncio.fixture
async def test_user_2():
    async with TestAsyncSessionLocal() as session:
        user = User(
            id="user_test_2",
            email="other@nexora.ai",
            username="otheruser",
            hashed_password=hash_password("MySecretPassword123"),
            is_active=True,
            is_verified=True,
            role="user",
        )
        session.add(user)
        profile = Profile(user_id=user.id, display_name="Other User")
        prefs = UserPreference(user_id=user.id, theme="light", default_model="nexora-pro")
        session.add(profile)
        session.add(prefs)
        await session.commit()
        await session.refresh(user)
        return user


@pytest_asyncio.fixture
async def test_admin_user():
    async with TestAsyncSessionLocal() as session:
        user = User(
            id="admin_test_1",
            email="admin@nexora.ai",
            username="nexoraadmin",
            hashed_password=hash_password("AdminSecretPassword123!"),
            is_active=True,
            is_verified=True,
            role="admin",
        )
        session.add(user)
        profile = Profile(user_id=user.id, display_name="NEXORA Admin")
        prefs = UserPreference(user_id=user.id, theme="dark", default_model="nexora-flagship")
        session.add(profile)
        session.add(prefs)
        await session.commit()
        await session.refresh(user)
        return user


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user_2(test_user_2):
    token = create_access_token(test_user_2.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(test_admin_user):
    token = create_access_token(test_admin_user.id)
    return {"Authorization": f"Bearer {token}"}
