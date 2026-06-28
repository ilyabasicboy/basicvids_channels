# BasicVids Channels

Channels microservice for BasicVids.

This service owns creator channels, channel playlists, playlist videos, channel subscriptions, and channel avatars.

## Stack

- Gunicorn
- FastAPI
- SQLModel
- Redis

## Development

Use a virtual environment:

```bash
virtualenv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run tests:

```bash
pytest
```

Run locally:

```bash
uvicorn basicvids_channels.main:app --reload
```

## Container

```bash
mkdir -p data
cp .env.example data/.env
docker compose up -d --build
```

The service is available through the shared gateway at:

```text
http://localhost:8080/api/v1/channels/
```

## Configuration

Project environment is loaded from:

```text
./data/.env
```

Start from:

```text
./.env.example
```

Database examples:

```env
# SQLite default
# DATABASE_URL=sqlite:///./data/database.db

# PostgreSQL example
DATABASE_URL=postgresql://basicvids_channels_user:change_me@host.docker.internal:5432/basicvids_channels
```

Important variables:

| Variable | Default | Description |
| --- | --- | --- |
| `DATA_PATH` | `./data` | Data directory mounted in container |
| `DATABASE_URL` | `sqlite:///./data/database.db` | Metadata database URL |
| `REDIS_URL` | `redis://localhost:6379/5` | Redis connection |
| `AUTH_CURRENT_USER_URL` | `http://basicvids_auth:8000/api/v1/users/detail/` | Auth service current-user endpoint |
| `MAX_CHANNEL_AVATAR_SIZE_BYTES` | `5242880` | Maximum channel avatar size |

## Healthcheck

```text
http://localhost:8080/channels/health
```

## Routes

| Route | Description |
| --- | --- |
| `/api/v1/channels/` | Create and list channels |
| `/api/v1/channels/me/` | Current user's channels |
| `/api/v1/channels/{channel_id}` | Read, update, and delete a channel |
| `/api/v1/channels/{channel_id}/avatar/` | Upload or delete channel avatar |
| `/api/v1/channels/{channel_id}/avatar/image/` | Display channel avatar |
| `/api/v1/channels/{channel_id}/subscriptions/` | Subscribe or unsubscribe |
| `/api/v1/channels/{channel_id}/videos/` | Channel videos |
| `/api/v1/channels/{channel_id}/playlists/` | Channel playlists |
| `/api/v1/channels/{channel_id}/playlists/{playlist_id}/videos/{video_id}` | Playlist videos |
