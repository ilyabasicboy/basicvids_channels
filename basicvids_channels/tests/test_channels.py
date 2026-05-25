from pathlib import Path
from tempfile import TemporaryDirectory

from sqlmodel import Session, delete, select
import httpx
import pytest

from basicvids_channels.auth import CurrentUser, get_current_user
from basicvids_channels.schemas.channels import Channel, ChannelAvatar, ChannelPlaylist, ChannelPlaylistItem, ChannelSubscription, ChannelVideo
from basicvids_channels.settings import settings
from basicvids_channels.tests import app, engine


pytestmark = pytest.mark.anyio
temporary_directory = TemporaryDirectory()
settings.DATA_PATH = Path(temporary_directory.name)


async def request(method: str, url: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, url, **kwargs)


def user(user_id: int = 1, is_admin: bool = False) -> CurrentUser:
    return CurrentUser(
        id=user_id,
        username=f"user-{user_id}",
        first_name="Test",
        last_name="Creator",
        email=f"user-{user_id}@example.com",
        is_admin=is_admin,
        email_confirmed=True,
    )


def set_current_user(current_user: CurrentUser) -> None:
    async def override_get_current_user():
        return current_user

    app.dependency_overrides[get_current_user] = override_get_current_user


class BaseTestChannels:
    method_url = "/api/v1/channels/"

    def setup_method(self):
        set_current_user(user(user_id=1))
        with Session(engine) as session:
            session.exec(delete(ChannelPlaylistItem))
            session.exec(delete(ChannelPlaylist))
            session.exec(delete(ChannelSubscription))
            session.exec(delete(ChannelVideo))
            session.exec(delete(ChannelAvatar))
            session.exec(delete(Channel))
            session.commit()
        avatar_directory = settings.DATA_PATH / "channel_avatars"
        if avatar_directory.exists():
            for file_path in avatar_directory.iterdir():
                file_path.unlink()

    async def create_channel(self, name: str = "Creator channel") -> dict:
        response = await request("POST", self.method_url, json={"name": name, "description": "About channel"})
        assert response.status_code == 201
        return response.json()

    async def create_playlist(self, channel_id: str, title: str = "Main playlist") -> dict:
        response = await request(
            "POST",
            f"{self.method_url}{channel_id}/playlists/",
            json={"title": title, "description": "Playlist description"},
        )
        assert response.status_code == 201
        return response.json()


class TestChannels(BaseTestChannels):
    async def test_user_can_create_channel(self):
        response = await request("POST", self.method_url, json={"name": "Creator channel"})

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Creator channel"
        assert body["slug"] == "creator-channel"
        assert body["owner_id"] == 1
        assert body["subscribers_count"] == 0

    async def test_channel_slug_must_be_unique(self):
        await self.create_channel()

        response = await request("POST", self.method_url, json={"name": "Creator channel"})

        assert response.status_code == 409

    async def test_non_owner_cannot_change_channel(self):
        channel = await self.create_channel()
        set_current_user(user(user_id=2))

        response = await request("PATCH", f"{self.method_url}{channel['id']}", json={"name": "Changed"})

        assert response.status_code == 403

    async def test_owner_can_upload_and_replace_channel_avatar(self):
        channel = await self.create_channel()

        response = await request(
            "PUT",
            f"{self.method_url}{channel['id']}/avatar/",
            files={"avatar": ("channel.png", b"first-avatar", "image/png")},
        )

        assert response.status_code == 200
        assert response.json()["content_type"] == "image/png"

        response = await request("GET", f"{self.method_url}{channel['id']}/avatar/image/")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content == b"first-avatar"

        response = await request(
            "PUT",
            f"{self.method_url}{channel['id']}/avatar/",
            files={"avatar": ("channel.jpg", b"second-avatar", "image/jpeg")},
        )

        assert response.status_code == 200
        assert len(list((settings.DATA_PATH / "channel_avatars").iterdir())) == 1

        response = await request("GET", f"{self.method_url}{channel['id']}/avatar/image/")

        assert response.headers["content-type"] == "image/jpeg"
        assert response.content == b"second-avatar"

    async def test_non_owner_cannot_change_channel_avatar(self):
        channel = await self.create_channel()
        set_current_user(user(user_id=2))

        response = await request(
            "PUT",
            f"{self.method_url}{channel['id']}/avatar/",
            files={"avatar": ("channel.png", b"avatar", "image/png")},
        )

        assert response.status_code == 403

    async def test_missing_channel_avatar_returns_placeholder(self):
        channel = await self.create_channel()

        response = await request("GET", f"{self.method_url}{channel['id']}/avatar/image/")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/svg+xml"
        assert "<svg" in response.text

    async def test_only_channel_owner_can_create_playlist(self):
        channel = await self.create_channel()
        set_current_user(user(user_id=2))

        response = await request("POST", f"{self.method_url}{channel['id']}/playlists/", json={"title": "Other"})

        assert response.status_code == 403

    async def test_owner_can_create_playlist_and_add_any_video_id(self):
        channel = await self.create_channel()
        playlist = await self.create_playlist(channel["id"])

        response = await request("POST", f"{self.method_url}{channel['id']}/playlists/{playlist['id']}/videos/video-123")

        assert response.status_code == 201
        body = response.json()
        assert body["videos_count"] == 1
        assert body["items"][0]["video_id"] == "video-123"

    async def test_owner_can_add_video_to_channel(self):
        channel = await self.create_channel()

        response = await request("POST", f"{self.method_url}{channel['id']}/videos/video-123")

        assert response.status_code == 201
        assert response.json()["video_id"] == "video-123"

        response = await request("GET", f"{self.method_url}{channel['id']}/videos/")

        assert response.status_code == 200
        assert response.json()["count"] == 1

    async def test_non_owner_cannot_add_video_to_channel(self):
        channel = await self.create_channel()
        set_current_user(user(user_id=2))

        response = await request("POST", f"{self.method_url}{channel['id']}/videos/video-123")

        assert response.status_code == 403

    async def test_duplicate_video_in_playlist_is_rejected(self):
        channel = await self.create_channel()
        playlist = await self.create_playlist(channel["id"])
        await request("POST", f"{self.method_url}{channel['id']}/playlists/{playlist['id']}/videos/video-123")

        response = await request("POST", f"{self.method_url}{channel['id']}/playlists/{playlist['id']}/videos/video-123")

        assert response.status_code == 409

    async def test_user_can_subscribe_and_unsubscribe_to_other_channel(self):
        channel = await self.create_channel()
        set_current_user(user(user_id=2))

        response = await request("POST", f"{self.method_url}{channel['id']}/subscriptions/")

        assert response.status_code == 201
        assert response.json()["user_id"] == 2

        response = await request("DELETE", f"{self.method_url}{channel['id']}/subscriptions/")

        assert response.status_code == 200
        with Session(engine) as session:
            assert session.exec(select(ChannelSubscription)).all() == []

    async def test_user_cannot_subscribe_to_own_channel(self):
        channel = await self.create_channel()

        response = await request("POST", f"{self.method_url}{channel['id']}/subscriptions/")

        assert response.status_code == 400

    async def test_delete_channel_removes_playlists_items_and_subscriptions(self):
        channel = await self.create_channel()
        playlist = await self.create_playlist(channel["id"])
        await request("POST", f"{self.method_url}{channel['id']}/playlists/{playlist['id']}/videos/video-123")
        await request(
            "PUT",
            f"{self.method_url}{channel['id']}/avatar/",
            files={"avatar": ("channel.png", b"avatar", "image/png")},
        )
        set_current_user(user(user_id=2))
        await request("POST", f"{self.method_url}{channel['id']}/subscriptions/")
        set_current_user(user(user_id=1))

        response = await request("DELETE", f"{self.method_url}{channel['id']}")

        assert response.status_code == 200
        with Session(engine) as session:
            assert session.exec(select(Channel)).all() == []
            assert session.exec(select(ChannelPlaylist)).all() == []
            assert session.exec(select(ChannelPlaylistItem)).all() == []
            assert session.exec(select(ChannelSubscription)).all() == []
            assert session.exec(select(ChannelVideo)).all() == []
            assert session.exec(select(ChannelAvatar)).all() == []
        assert list((settings.DATA_PATH / "channel_avatars").iterdir()) == []
