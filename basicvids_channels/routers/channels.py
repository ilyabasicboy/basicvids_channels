import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, delete, select

from basicvids_channels.auth import CurrentUser, get_current_user
from basicvids_channels.db import get_session
from basicvids_channels.models.channels import (
    ChannelChange,
    ChannelCreate,
    ChannelList,
    ChannelPlaylistChange,
    ChannelPlaylistCreate,
    ChannelPlaylistItemChange,
    ChannelPlaylistItemPublic,
    ChannelPlaylistList,
    ChannelPlaylistPublic,
    ChannelPublic,
    ChannelVideoList,
    ChannelVideoPublic,
    DeleteResponse,
    SubscriptionList,
    SubscriptionPublic,
    VideoChannelPublic,
    VideoChannelsRequest,
    VideoChannelsResponse,
)
from basicvids_channels.rate_limit import client_identifier, enforce_rate_limit
from basicvids_channels.schemas.channels import (
    Channel,
    ChannelPlaylist,
    ChannelPlaylistItem,
    ChannelSubscription,
    ChannelVideo,
    utc_now,
)


router = APIRouter(tags=["Channels"], prefix="/channels")
SLUG_PATTERN = re.compile(r"[^a-z0-9-]+")


def normalize_name(name: str) -> str:
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Channel name is required")
    if len(clean_name) > 120:
        raise HTTPException(status_code=400, detail="Channel name is too long")
    return clean_name


def normalize_description(description: str | None) -> str | None:
    if description is None:
        return None
    clean_description = description.strip()
    if len(clean_description) > 2000:
        raise HTTPException(status_code=400, detail="Description is too long")
    return clean_description or None


def slugify(value: str) -> str:
    slug = SLUG_PATTERN.sub("-", value.strip().lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug:
        raise HTTPException(status_code=400, detail="Channel slug is required")
    if len(slug) > 140:
        raise HTTPException(status_code=400, detail="Channel slug is too long")
    return slug


def normalize_playlist_title(title: str) -> str:
    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="Playlist title is required")
    if len(clean_title) > 255:
        raise HTTPException(status_code=400, detail="Playlist title is too long")
    return clean_title


def get_channel_or_404(session: Session, channel_id: str) -> Channel:
    channel = session.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


def get_playlist_or_404(session: Session, channel_id: str, playlist_id: str) -> ChannelPlaylist:
    playlist = session.get(ChannelPlaylist, playlist_id)
    if not playlist or playlist.channel_id != channel_id:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return playlist


def ensure_channel_owner(channel: Channel, current_user: CurrentUser) -> None:
    if channel.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the channel creator can manage this channel")


def channel_to_public(
    session: Session,
    channel: Channel,
    current_user: CurrentUser | None = None,
    subscribers_count: int | None = None,
    playlists_count: int | None = None,
    videos_count: int | None = None,
) -> ChannelPublic:
    if subscribers_count is None:
        subscribers_count = session.exec(
            select(func.count()).select_from(ChannelSubscription).where(ChannelSubscription.channel_id == channel.id)
        ).one()
    if playlists_count is None:
        playlists_count = session.exec(
            select(func.count()).select_from(ChannelPlaylist).where(ChannelPlaylist.channel_id == channel.id)
        ).one()
    if videos_count is None:
        videos_count = session.exec(
            select(func.count()).select_from(ChannelVideo).where(ChannelVideo.channel_id == channel.id)
        ).one()

    is_subscribed = False
    if current_user:
        is_subscribed = session.exec(
            select(ChannelSubscription.id).where(
                ChannelSubscription.channel_id == channel.id,
                ChannelSubscription.user_id == current_user.id,
            )
        ).first() is not None

    result = ChannelPublic.model_validate(channel)
    result.subscribers_count = subscribers_count
    result.playlists_count = playlists_count
    result.videos_count = videos_count
    result.is_subscribed = is_subscribed
    return result


def playlist_to_public(
    session: Session,
    playlist: ChannelPlaylist,
    include_items: bool = False,
    videos_count: int | None = None,
) -> ChannelPlaylistPublic:
    if videos_count is None:
        videos_count = session.exec(
            select(func.count()).select_from(ChannelPlaylistItem).where(ChannelPlaylistItem.playlist_id == playlist.id)
        ).one()

    result = ChannelPlaylistPublic.model_validate(playlist)
    result.videos_count = videos_count
    if include_items:
        items = session.exec(
            select(ChannelPlaylistItem)
            .where(ChannelPlaylistItem.playlist_id == playlist.id)
            .order_by(ChannelPlaylistItem.position, ChannelPlaylistItem.created_at)
        ).all()
        result.items = [ChannelPlaylistItemPublic.model_validate(item) for item in items]
    return result


@router.get("/", response_model=ChannelList)
async def list_channels(
    owner_id: int | None = Query(default=None, ge=1),
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    session: Session = Depends(get_session),
) -> ChannelList:
    filters = []
    if owner_id is not None:
        filters.append(Channel.owner_id == owner_id)
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(or_(Channel.name.ilike(pattern), Channel.description.ilike(pattern), Channel.slug.ilike(pattern)))

    statement = select(Channel)
    count_statement = select(func.count()).select_from(Channel)
    for item_filter in filters:
        statement = statement.where(item_filter)
        count_statement = count_statement.where(item_filter)

    channels = session.exec(
        statement.order_by(col(Channel.updated_at).desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    count = session.exec(count_statement).one()

    return ChannelList(
        channels=[channel_to_public(session, channel) for channel in channels],
        count=count,
    )


@router.get("/me/", response_model=ChannelList)
async def list_my_channels(
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ChannelList:
    channels = session.exec(select(Channel).where(Channel.owner_id == current_user.id).order_by(col(Channel.updated_at).desc())).all()
    return ChannelList(
        channels=[channel_to_public(session, channel, current_user) for channel in channels],
        count=len(channels),
    )


@router.get("/subscriptions/me/", response_model=SubscriptionList)
async def list_my_subscriptions(
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SubscriptionList:
    subscriptions = session.exec(
        select(ChannelSubscription)
        .where(ChannelSubscription.user_id == current_user.id)
        .order_by(col(ChannelSubscription.created_at).desc())
    ).all()
    return SubscriptionList(
        subscriptions=[SubscriptionPublic.model_validate(item) for item in subscriptions],
        count=len(subscriptions),
    )


@router.get("/videos/{video_id}/channel", response_model=ChannelPublic)
async def get_channel_by_video(
    video_id: str,
    session: Session = Depends(get_session),
) -> ChannelPublic:
    channel_video = session.exec(select(ChannelVideo).where(ChannelVideo.video_id == video_id)).first()
    if not channel_video:
        raise HTTPException(status_code=404, detail="Video channel not found")

    channel = get_channel_or_404(session, channel_video.channel_id)
    return channel_to_public(session, channel)


@router.post("/videos/channels", response_model=VideoChannelsResponse)
async def get_channels_by_videos(
    data: VideoChannelsRequest,
    session: Session = Depends(get_session),
) -> VideoChannelsResponse:
    video_ids = list(dict.fromkeys([video_id for video_id in data.video_ids if video_id]))
    if not video_ids:
        return VideoChannelsResponse(items=[])

    channel_videos = session.exec(select(ChannelVideo).where(col(ChannelVideo.video_id).in_(video_ids))).all()
    channel_ids = list(dict.fromkeys([item.channel_id for item in channel_videos]))
    channels = session.exec(select(Channel).where(col(Channel.id).in_(channel_ids))).all() if channel_ids else []
    channels_by_id = {channel.id: channel_to_public(session, channel) for channel in channels}

    return VideoChannelsResponse(
        items=[
            VideoChannelPublic(video_id=item.video_id, channel=channels_by_id[item.channel_id])
            for item in channel_videos
            if item.channel_id in channels_by_id
        ],
    )


@router.post("/", response_model=ChannelPublic, status_code=201)
async def create_channel(
    data: ChannelCreate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ChannelPublic:
    await enforce_rate_limit("create_channel_ip", client_identifier(request), 60, 3600)
    await enforce_rate_limit("create_channel_user", f"user:{current_user.id}", 20, 3600)

    name = normalize_name(data.name)
    channel = Channel(
        name=name,
        slug=slugify(data.slug or name),
        description=normalize_description(data.description),
        owner_id=current_user.id,
        owner_username=current_user.username,
        owner_first_name=current_user.first_name,
        owner_last_name=current_user.last_name,
    )
    session.add(channel)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Channel slug is already used")

    session.refresh(channel)
    return channel_to_public(session, channel, current_user)


@router.get("/{channel_id}", response_model=ChannelPublic)
async def get_channel(
    channel_id: str,
    session: Session = Depends(get_session),
) -> ChannelPublic:
    channel = get_channel_or_404(session, channel_id)
    return channel_to_public(session, channel)


@router.patch("/{channel_id}", response_model=ChannelPublic)
async def change_channel(
    channel_id: str,
    data: ChannelChange,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ChannelPublic:
    channel = get_channel_or_404(session, channel_id)
    ensure_channel_owner(channel, current_user)

    if "name" in data.model_fields_set:
        channel.name = normalize_name(data.name or "")
    if "slug" in data.model_fields_set:
        channel.slug = slugify(data.slug or channel.name)
    if "description" in data.model_fields_set:
        channel.description = normalize_description(data.description)
    channel.updated_at = utc_now()

    session.add(channel)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Channel slug is already used")

    session.refresh(channel)
    return channel_to_public(session, channel, current_user)


@router.delete("/{channel_id}", response_model=DeleteResponse)
async def delete_channel(
    channel_id: str,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> DeleteResponse:
    channel = get_channel_or_404(session, channel_id)
    ensure_channel_owner(channel, current_user)

    playlists = session.exec(select(ChannelPlaylist).where(ChannelPlaylist.channel_id == channel_id)).all()
    for playlist in playlists:
        session.exec(delete(ChannelPlaylistItem).where(ChannelPlaylistItem.playlist_id == playlist.id))
        session.delete(playlist)
    session.exec(delete(ChannelSubscription).where(ChannelSubscription.channel_id == channel_id))
    session.exec(delete(ChannelVideo).where(ChannelVideo.channel_id == channel_id))
    session.delete(channel)
    session.commit()
    return DeleteResponse(message="Channel deleted successfully")


@router.get("/{channel_id}/subscriptions/", response_model=SubscriptionList)
async def list_channel_subscriptions(
    channel_id: str,
    session: Session = Depends(get_session),
) -> SubscriptionList:
    get_channel_or_404(session, channel_id)
    subscriptions = session.exec(
        select(ChannelSubscription)
        .where(ChannelSubscription.channel_id == channel_id)
        .order_by(col(ChannelSubscription.created_at).desc())
    ).all()
    return SubscriptionList(
        subscriptions=[SubscriptionPublic.model_validate(item) for item in subscriptions],
        count=len(subscriptions),
    )


@router.post("/{channel_id}/subscriptions/", response_model=SubscriptionPublic, status_code=201)
async def subscribe_to_channel(
    channel_id: str,
    request: Request,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ChannelSubscription:
    await enforce_rate_limit("subscribe_channel_user", f"user:{current_user.id}", 120, 3600)
    channel = get_channel_or_404(session, channel_id)
    if channel.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot subscribe to your own channel")

    subscription = ChannelSubscription(
        channel_id=channel_id,
        user_id=current_user.id,
        username=current_user.username,
    )
    session.add(subscription)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Already subscribed to this channel")

    session.refresh(subscription)
    return subscription


@router.delete("/{channel_id}/subscriptions/", response_model=DeleteResponse)
async def unsubscribe_from_channel(
    channel_id: str,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> DeleteResponse:
    subscription = session.exec(
        select(ChannelSubscription).where(
            ChannelSubscription.channel_id == channel_id,
            ChannelSubscription.user_id == current_user.id,
        )
    ).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    session.delete(subscription)
    session.commit()
    return DeleteResponse(message="Subscription deleted successfully")


@router.get("/{channel_id}/videos/", response_model=ChannelVideoList)
async def list_channel_videos(
    channel_id: str,
    session: Session = Depends(get_session),
) -> ChannelVideoList:
    get_channel_or_404(session, channel_id)
    videos = session.exec(
        select(ChannelVideo)
        .where(ChannelVideo.channel_id == channel_id)
        .order_by(col(ChannelVideo.created_at).desc())
    ).all()
    return ChannelVideoList(
        videos=[ChannelVideoPublic.model_validate(video) for video in videos],
        count=len(videos),
    )


@router.post("/{channel_id}/videos/{video_id}", response_model=ChannelVideoPublic, status_code=201)
async def add_video_to_channel(
    channel_id: str,
    video_id: str,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ChannelVideo:
    channel = get_channel_or_404(session, channel_id)
    ensure_channel_owner(channel, current_user)

    channel_video = ChannelVideo(
        channel_id=channel_id,
        video_id=video_id,
        added_by_user_id=current_user.id,
    )
    channel.updated_at = utc_now()
    session.add(channel_video)
    session.add(channel)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Video is already in this channel")

    session.refresh(channel_video)
    return channel_video


@router.delete("/{channel_id}/videos/{video_id}", response_model=DeleteResponse)
async def remove_video_from_channel(
    channel_id: str,
    video_id: str,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> DeleteResponse:
    channel = get_channel_or_404(session, channel_id)
    ensure_channel_owner(channel, current_user)
    channel_video = session.exec(
        select(ChannelVideo).where(ChannelVideo.channel_id == channel_id, ChannelVideo.video_id == video_id)
    ).first()
    if not channel_video:
        raise HTTPException(status_code=404, detail="Channel video not found")

    session.delete(channel_video)
    channel.updated_at = utc_now()
    session.add(channel)
    session.commit()
    return DeleteResponse(message="Channel video deleted successfully")


@router.get("/{channel_id}/playlists/", response_model=ChannelPlaylistList)
async def list_channel_playlists(
    channel_id: str,
    session: Session = Depends(get_session),
) -> ChannelPlaylistList:
    get_channel_or_404(session, channel_id)
    playlists = session.exec(
        select(ChannelPlaylist).where(ChannelPlaylist.channel_id == channel_id).order_by(col(ChannelPlaylist.updated_at).desc())
    ).all()
    return ChannelPlaylistList(
        playlists=[playlist_to_public(session, playlist) for playlist in playlists],
        count=len(playlists),
    )


@router.post("/{channel_id}/playlists/", response_model=ChannelPlaylistPublic, status_code=201)
async def create_channel_playlist(
    channel_id: str,
    data: ChannelPlaylistCreate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ChannelPlaylistPublic:
    channel = get_channel_or_404(session, channel_id)
    ensure_channel_owner(channel, current_user)

    playlist = ChannelPlaylist(
        channel_id=channel_id,
        title=normalize_playlist_title(data.title),
        description=normalize_description(data.description),
    )
    channel.updated_at = utc_now()
    session.add(playlist)
    session.add(channel)
    session.commit()
    session.refresh(playlist)
    return playlist_to_public(session, playlist)


@router.get("/{channel_id}/playlists/{playlist_id}", response_model=ChannelPlaylistPublic)
async def get_channel_playlist(
    channel_id: str,
    playlist_id: str,
    session: Session = Depends(get_session),
) -> ChannelPlaylistPublic:
    get_channel_or_404(session, channel_id)
    playlist = get_playlist_or_404(session, channel_id, playlist_id)
    return playlist_to_public(session, playlist, include_items=True)


@router.patch("/{channel_id}/playlists/{playlist_id}", response_model=ChannelPlaylistPublic)
async def change_channel_playlist(
    channel_id: str,
    playlist_id: str,
    data: ChannelPlaylistChange,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ChannelPlaylistPublic:
    channel = get_channel_or_404(session, channel_id)
    ensure_channel_owner(channel, current_user)
    playlist = get_playlist_or_404(session, channel_id, playlist_id)

    if "title" in data.model_fields_set:
        playlist.title = normalize_playlist_title(data.title or "")
    if "description" in data.model_fields_set:
        playlist.description = normalize_description(data.description)
    playlist.updated_at = utc_now()
    channel.updated_at = utc_now()
    session.add(playlist)
    session.add(channel)
    session.commit()
    session.refresh(playlist)
    return playlist_to_public(session, playlist, include_items=True)


@router.delete("/{channel_id}/playlists/{playlist_id}", response_model=DeleteResponse)
async def delete_channel_playlist(
    channel_id: str,
    playlist_id: str,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> DeleteResponse:
    channel = get_channel_or_404(session, channel_id)
    ensure_channel_owner(channel, current_user)
    playlist = get_playlist_or_404(session, channel_id, playlist_id)

    session.exec(delete(ChannelPlaylistItem).where(ChannelPlaylistItem.playlist_id == playlist.id))
    session.delete(playlist)
    channel.updated_at = utc_now()
    session.add(channel)
    session.commit()
    return DeleteResponse(message="Playlist deleted successfully")


@router.post("/{channel_id}/playlists/{playlist_id}/videos/{video_id}", response_model=ChannelPlaylistPublic, status_code=201)
async def add_video_to_channel_playlist(
    channel_id: str,
    playlist_id: str,
    video_id: str,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ChannelPlaylistPublic:
    channel = get_channel_or_404(session, channel_id)
    ensure_channel_owner(channel, current_user)
    playlist = get_playlist_or_404(session, channel_id, playlist_id)

    next_position = session.exec(
        select(func.coalesce(func.max(ChannelPlaylistItem.position), -1)).where(ChannelPlaylistItem.playlist_id == playlist.id)
    ).one() + 1
    item = ChannelPlaylistItem(
        playlist_id=playlist.id,
        video_id=video_id,
        position=next_position,
        added_by_user_id=current_user.id,
    )
    playlist.updated_at = utc_now()
    channel.updated_at = utc_now()
    session.add(item)
    session.add(playlist)
    session.add(channel)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Video is already in this playlist")

    session.refresh(playlist)
    return playlist_to_public(session, playlist, include_items=True)


@router.patch("/{channel_id}/playlists/{playlist_id}/videos/{video_id}", response_model=ChannelPlaylistPublic)
async def change_channel_playlist_video_position(
    channel_id: str,
    playlist_id: str,
    video_id: str,
    data: ChannelPlaylistItemChange,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ChannelPlaylistPublic:
    channel = get_channel_or_404(session, channel_id)
    ensure_channel_owner(channel, current_user)
    playlist = get_playlist_or_404(session, channel_id, playlist_id)
    item = session.exec(
        select(ChannelPlaylistItem).where(ChannelPlaylistItem.playlist_id == playlist.id, ChannelPlaylistItem.video_id == video_id)
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Playlist video not found")

    item.position = data.position
    playlist.updated_at = utc_now()
    channel.updated_at = utc_now()
    session.add(item)
    session.add(playlist)
    session.add(channel)
    session.commit()
    session.refresh(playlist)
    return playlist_to_public(session, playlist, include_items=True)


@router.delete("/{channel_id}/playlists/{playlist_id}/videos/{video_id}", response_model=ChannelPlaylistPublic)
async def remove_video_from_channel_playlist(
    channel_id: str,
    playlist_id: str,
    video_id: str,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ChannelPlaylistPublic:
    channel = get_channel_or_404(session, channel_id)
    ensure_channel_owner(channel, current_user)
    playlist = get_playlist_or_404(session, channel_id, playlist_id)
    item = session.exec(
        select(ChannelPlaylistItem).where(ChannelPlaylistItem.playlist_id == playlist.id, ChannelPlaylistItem.video_id == video_id)
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Playlist video not found")

    session.delete(item)
    playlist.updated_at = utc_now()
    channel.updated_at = utc_now()
    session.add(playlist)
    session.add(channel)
    session.commit()
    session.refresh(playlist)
    return playlist_to_public(session, playlist, include_items=True)
