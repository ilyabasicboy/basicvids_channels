# BasicVids Channels

Channels service owns creator channels, channel playlists, playlist videos, and channel subscriptions.

## Routes

| Route | Description |
| ----- | ----------- |
| `/api/v1/channels/` | Create/list channels |
| `/api/v1/channels/me/` | Current user's channels |
| `/api/v1/channels/{channel_id}` | Read/update/delete channel |
| `/api/v1/channels/{channel_id}/avatar/` | Upload/delete channel avatar (owner only) |
| `/api/v1/channels/{channel_id}/avatar/image/` | Display channel avatar |
| `/api/v1/channels/{channel_id}/subscriptions/` | Subscribe/unsubscribe |
| `/api/v1/channels/{channel_id}/videos/` | Channel videos |
| `/api/v1/channels/{channel_id}/playlists/` | Channel playlists |
| `/api/v1/channels/{channel_id}/playlists/{playlist_id}/videos/{video_id}` | Playlist videos |
