# Zing Music provider for Music Assistant

Play [Zing Music](https://zingmusic.app) inside [Music Assistant](https://music-assistant.io/) using your normal Zing account.

## Requirements

- Music Assistant server (add-on or standalone)
- Active Zing Music subscription / account
- Same **email and password** you use at [zingmusic.app/signin](https://zingmusic.app/signin)

## Installation

1. Copy this folder to your Music Assistant **custom providers** directory:

   ```bash
   cp -r music_providers/zing /path/to/custom_providers/zing
   ```

2. Restart Music Assistant.

3. In Music Assistant: **Settings** → **Providers** → **Add provider** → **Zing Music**.

## Sign in

1. Enter your Zing **email** and **password**.
2. Click **Sign in**.
3. Click **Save** on the provider configuration page.

Credentials are exchanged with **Firebase Authentication** (same as the official Zing web app), then stored encrypted in Music Assistant. Your password is not kept after sign-in.

To switch accounts, use **Sign out**, then sign in again.

## What works

| Feature | Supported |
|---------|-----------|
| Search (tracks, albums, artists) | Yes |
| Library artists / albums / tracks | Yes |
| Playlists | Yes |
| Radio channels | Yes |
| Artist albums & top tracks | Yes |
| Playback | Yes |
| Google sign-in in MA | No (use email/password) |

## How it works

```text
Music Assistant  →  Firebase (email/password)  →  refresh token
                →  GraphQL API (jewishmusic.fm)  →  library metadata
                →  CDN (jewishmusic.fm)  →  MP3/audio stream
```

- **API:** `https://jewishmusic.fm:8443/graphql`
- **Auth:** Firebase Identity Toolkit (public API key used by the Zing web app)
- **Streams:** `https://jewishmusic.fm/wp-content/uploads/secretmusicfolder1/...` with Zing referer headers

## Configuration keys

Stored automatically after sign-in (do not edit unless debugging):

| Key | Purpose |
|-----|---------|
| `refresh_token` | Firebase refresh token (encrypted) |
| `access_token` | Firebase ID token for API calls (encrypted) |
| `user_id` | Firebase user ID for library queries |
| `expiry` | Token expiry timestamp |

## Troubleshooting

### `INVALID_REFRESH_TOKEN`

Tokens in storage may be invalid or corrupted.

1. Open provider settings → **Sign out**
2. **Sign in** again with email/password
3. **Save**
4. Reload the provider or restart Music Assistant

### Login OK, browse OK, playback fails

1. Ensure you have the latest provider code (uses `StreamType.CUSTOM` for streaming).
2. Restart Music Assistant after updating files.
3. Enable debug logging for the Zing provider and check for `Audio request failed` messages.

### Provider does not appear

- Folder must be named `zing` and contain `manifest.json`
- Path must be `custom_providers/zing` (not nested incorrectly)
- Restart Music Assistant after copying files

### Library empty

- Confirm sign-in succeeded (status message in settings)
- Run a library **Sync** in Music Assistant
- Library content is your Zing account favorites (same as in the app)

## Development

Active development path:

```text
/Users/avi/SandBox/Zing/home-assistant-addon/music_providers/zing/
```

Files:

- `__init__.py` — `ZingProvider`, GraphQL, library, `get_stream_details`, `get_audio_stream`
- `auth.py` — `login_with_email_password`, token refresh
- `constants.py` — config keys, media URL prefixes
- `manifest.json` — provider registration for Music Assistant

No extra Python packages are required beyond Music Assistant itself.

## Disclaimer

This is an unofficial community provider. It is not affiliated with Zing Music or JewishMusic.fm. Use in line with Zing’s terms of service.
