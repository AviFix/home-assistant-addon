"""Authentication helpers for the Zing music provider."""

from __future__ import annotations

import logging

import aiohttp
from music_assistant_models.errors import LoginFailed

FIREBASE_API_KEY = "AIzaSyByyRIbRvi6MLOjfWqdv73B88x2QsVkOZA"
FIREBASE_SIGN_IN_URL = (
    f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
    f"?key={FIREBASE_API_KEY}"
)
FIREBASE_TOKEN_URL = f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"

logger = logging.getLogger("music_assistant.providers.zing.auth")


class ZingAuthHelper:
    """Firebase authentication for Zing Music (same as zingmusic.app)."""

    @staticmethod
    def normalize_firebase_auth(data: dict) -> dict:
        """Normalize Firebase token payloads to a consistent shape."""
        expires_in = int(data.get("expiresIn") or data.get("expires_in") or 3600)
        refresh_token = data.get("refreshToken") or data.get("refresh_token")
        access_token = data.get("idToken") or data.get("id_token") or data.get("access_token")
        user_id = data.get("localId") or data.get("local_id") or data.get("user_id")
        if not refresh_token or not access_token:
            raise LoginFailed("Incomplete authentication response from Firebase")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": expires_in,
            "user_id": user_id,
        }

    @staticmethod
    async def login_with_email_password(email: str, password: str) -> dict:
        """Sign in with Zing email and password via Firebase."""
        if not email or not password:
            raise LoginFailed("Email and password are required")

        payload = {
            "email": email.strip(),
            "password": password,
            "returnSecureToken": True,
            "clientType": "CLIENT_TYPE_WEB",
        }
        headers = {"Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                FIREBASE_SIGN_IN_URL, json=payload, headers=headers
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    message = data.get("error", {}).get("message", str(data))
                    raise LoginFailed(f"Zing sign-in failed: {message}")

        return ZingAuthHelper.normalize_firebase_auth(data)

    @staticmethod
    async def refresh_firebase_token(refresh_token: str) -> dict:
        """Refresh Firebase tokens using a refresh token."""
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        async with aiohttp.ClientSession() as session:
            async with session.post(FIREBASE_TOKEN_URL, data=data, headers=headers) as resp:
                body = await resp.json()
                if resp.status != 200:
                    message = body.get("error", {}).get("message", str(body))
                    raise LoginFailed(f"Failed to refresh Zing token: {message}")
                return body

    @staticmethod
    async def login_with_refresh_token(refresh_token: str) -> dict:
        """Exchange a refresh token for fresh Firebase tokens."""
        if not refresh_token:
            raise LoginFailed("No refresh token configured")
        data = await ZingAuthHelper.refresh_firebase_token(refresh_token)
        return ZingAuthHelper.normalize_firebase_auth(data)
