from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChannelCreate(BaseModel):
    name: str
    slug: str | None = None
    description: str | None = None


class ChannelChange(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None


class ChannelPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: str | None = None
    owner_id: int
    owner_username: str | None = None
    owner_first_name: str | None = None
    owner_last_name: str | None = None
    subscribers_count: int = 0
    playlists_count: int = 0
    videos_count: int = 0
    is_subscribed: bool = False
    created_at: datetime
    updated_at: datetime


class ChannelList(BaseModel):
    channels: list[ChannelPublic]
    count: int


class SubscriptionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    channel_id: str
    user_id: int
    username: str | None = None
    created_at: datetime


class SubscriptionList(BaseModel):
    subscriptions: list[SubscriptionPublic]
    count: int


class ChannelPlaylistCreate(BaseModel):
    title: str
    description: str | None = None


class ChannelPlaylistChange(BaseModel):
    title: str | None = None
    description: str | None = None


class ChannelPlaylistItemChange(BaseModel):
    position: int = Field(ge=0)


class ChannelVideoPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    channel_id: str
    video_id: str
    added_by_user_id: int
    created_at: datetime


class ChannelVideoList(BaseModel):
    videos: list[ChannelVideoPublic]
    count: int


class ChannelPlaylistItemPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    playlist_id: str
    video_id: str
    position: int
    added_by_user_id: int
    created_at: datetime


class ChannelPlaylistPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    channel_id: str
    title: str
    description: str | None = None
    videos_count: int = 0
    items: list[ChannelPlaylistItemPublic] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ChannelPlaylistList(BaseModel):
    playlists: list[ChannelPlaylistPublic]
    count: int


class DeleteResponse(BaseModel):
    message: str
