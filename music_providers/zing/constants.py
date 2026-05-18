"""Constants for the Zing music provider."""

from __future__ import annotations

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_ACCESS_TOKEN = "access_token"
CONF_USER_ID = "user_id"
CONF_EXPIRY = "expiry"

CONF_ACTION_LOGIN = "login"
CONF_ACTION_CLEAR_AUTH = "clear_auth"

# Refresh Firebase tokens this many seconds before they expire.
TOKEN_REFRESH_BUFFER = 300

MEDIA_BASE_URL = "https://jewishmusic.fm"
MEDIA_UPLOAD_PREFIX = "/wp-content/uploads/secretmusicfolder1"
