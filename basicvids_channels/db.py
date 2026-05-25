from sqlmodel import Session, SQLModel, create_engine

from basicvids_channels.schemas.channels import (
    Channel,
    ChannelAvatar,
    ChannelPlaylist,
    ChannelPlaylistItem,
    ChannelSubscription,
    ChannelVideo,
)
from basicvids_channels.settings import settings


engine = create_engine(settings.DATABASE_URL)


def create_db_and_tables():
    settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)


async def get_session():
    with Session(engine) as session:
        yield session
