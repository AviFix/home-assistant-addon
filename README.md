# Music Assistant (Home Assistant) + Zing Music provider

This repository contains:

1. **Music Assistant** — Home Assistant add-on to run the [Music Assistant](https://music-assistant.io/) server
2. **Zing Music provider** — custom Music Assistant provider for [Zing Music](https://zingmusic.app) (Jewish music streaming)

> **Development path:** `/Users/avi/SandBox/Zing/home-assistant-addon`  
> Make all changes here (not the older `2026/home-assistant-addon` copy).

---

## Music Assistant add-on

Music Assistant is a music library manager for your local and online sources, integrated with Home Assistant.

- **Documentation:** https://music-assistant.io/
- **Support:** https://github.com/music-assistant/support

### Install the add-on repository

[![Open your Home Assistant instance and add this repository.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fmusic-assistant%2Fhome-assistant-addon)

Or add manually: [Installing third-party add-ons](https://www.home-assistant.io/hassio/installing_third_party_addons).

Official upstream repository: https://github.com/music-assistant/home-assistant-addon

---

## Zing Music provider

Stream your Zing Music library in Music Assistant using the **same email and password** as [zingmusic.app](https://zingmusic.app/signin).

### Features

- Search (English and Hebrew)
- Library: artists, albums, tracks, playlists, radio
- Playback via Zing’s CDN (authenticated streams)
- Multiple provider instances supported

### Install the Zing provider

Music Assistant loads custom providers from a `custom_providers` folder.

**Option A — Music Assistant add-on (recommended)**

Copy the provider into the add-on’s custom providers directory on your Home Assistant host, then restart Music Assistant:

```bash
# Adjust the destination path for your setup
cp -r music_providers/zing /path/to/music_assistant/custom_providers/zing
```

**Option B — Bind mount / dev setup**

If your add-on or Docker setup mounts `music_providers`, place the `zing` folder there.

**Option C — Music Assistant server source tree**

```bash
cp -r music_providers/zing /path/to/music-assistant-server/music_assistant/providers/zing
```

### Configure Zing in Music Assistant

1. Open **Music Assistant** → **Settings** → **Providers**
2. Click **Add provider** → **Zing Music**
3. Enter your **Zing email** and **password**
4. Click **Sign in**, then **Save**
5. Run **Sync** if needed, then browse or search your library

Full details: [music_providers/zing/README.md](music_providers/zing/README.md)

### Zing provider layout

```
music_providers/zing/
├── __init__.py      # Provider logic (GraphQL, library, playback)
├── auth.py          # Firebase email/password authentication
├── constants.py     # Config keys and API constants
├── manifest.json    # Music Assistant provider manifest
├── icon.svg         # Provider icon
└── README.md        # Provider documentation
```

---

## Repository contents

| Path | Description |
|------|-------------|
| `music_assistant/` | Home Assistant add-on definition |
| `music_providers/zing/` | Zing Music provider for Music Assistant |
| `ytm_po_token_generator/` | YouTube Music PO token helper add-on (upstream) |
| `repository.json` | Add-on repository metadata |

---

## Troubleshooting

| Issue | What to try |
|-------|-------------|
| `INVALID_REFRESH_TOKEN` | Sign out in provider settings → Sign in again → Save |
| Login works, no playback | Update to latest `music_providers/zing` and restart MA |
| Provider not listed | Confirm `zing` is under `custom_providers/` and restart |

Enable **debug** logging for the Zing provider in Music Assistant settings for more detail.

---

## License

Music Assistant components follow the upstream project licenses. The Zing provider is community-maintained; Zing Music and Firebase authentication are services of their respective owners.
