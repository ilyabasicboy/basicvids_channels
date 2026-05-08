from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from basicvids_channels.db import get_session
from basicvids_channels.main import app


TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

SQLModel.metadata.create_all(engine)


async def override_get_session():
    with Session(engine) as session:
        yield session


app.dependency_overrides[get_session] = override_get_session
