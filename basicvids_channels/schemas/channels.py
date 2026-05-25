from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Channel(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("slug", name="uq_channel_slug"),)

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str = Field(max_length=120)
    slug: str = Field(max_length=140, index=True)
    description: str | None = Field(default=None, max_length=2000)
    owner_id: int = Field(index=True)
    owner_username: str | None = Field(default=None, max_length=100)
    owner_first_name: str | None = Field(default=None, max_length=100)
    owner_last_name: str | None = Field(default=None, max_length=100)
    created_at: datetime = Field(sa_type=DateTime(timezone=True), default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(sa_type=DateTime(timezone=True), default_factory=utc_now, nullable=False)


class ChannelAvatar(SQLModel, table=True):
    channel_id: str = Field(foreign_key="channel.id", primary_key=True)
    storage_key: str = Field(unique=True, max_length=500)
    content_type: str = Field(max_length=100)
    size_bytes: int = Field(ge=0)
    created_at: datetime = Field(sa_type=DateTime(timezone=True), default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(sa_type=DateTime(timezone=True), default_factory=utc_now, nullable=False)


class ChannelSubscription(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("channel_id", "user_id", name="uq_channel_subscription_channel_user"),)

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    channel_id: str = Field(foreign_key="channel.id", index=True)
    user_id: int = Field(index=True)
    username: str | None = Field(default=None, max_length=100)
    created_at: datetime = Field(sa_type=DateTime(timezone=True), default_factory=utc_now, nullable=False)


class ChannelPlaylist(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    channel_id: str = Field(foreign_key="channel.id", index=True)
    title: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    created_at: datetime = Field(sa_type=DateTime(timezone=True), default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(sa_type=DateTime(timezone=True), default_factory=utc_now, nullable=False)


class ChannelVideo(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("channel_id", "video_id", name="uq_channel_video_channel_video"),)

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    channel_id: str = Field(foreign_key="channel.id", index=True)
    video_id: str = Field(index=True, max_length=100)
    added_by_user_id: int = Field(index=True)
    created_at: datetime = Field(sa_type=DateTime(timezone=True), default_factory=utc_now, nullable=False)


class ChannelPlaylistItem(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("playlist_id", "video_id", name="uq_channel_playlist_item_playlist_video"),)

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    playlist_id: str = Field(foreign_key="channelplaylist.id", index=True)
    video_id: str = Field(index=True, max_length=100)
    position: int = Field(ge=0, index=True)
    added_by_user_id: int = Field(index=True)
    created_at: datetime = Field(sa_type=DateTime(timezone=True), default_factory=utc_now, nullable=False)
