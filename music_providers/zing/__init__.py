"""Zing music provider for Music Assistant."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from aiohttp import ClientResponseError
from music_assistant_models.config_entries import ConfigEntry, ConfigValueType
from music_assistant_models.enums import (
    ContentType,
    ImageType,
    MediaType,
    ProviderFeature,
    StreamType,
    ConfigEntryType,
)
from music_assistant_models.errors import LoginFailed, ProviderUnavailableError
from music_assistant_models.media_items import (
    Album,
    Artist,
    AudioFormat,
    Playlist,
    ProviderMapping,
    Radio,
    SearchResults,
    Track,
    UniqueList,
)
from music_assistant_models.streamdetails import StreamDetails

from music_assistant.models.music_provider import MusicProvider

from .auth import ZingAuthHelper
from .constants import (
    CONF_ACCESS_TOKEN,
    CONF_ACTION_CLEAR_AUTH,
    CONF_ACTION_LOGIN,
    CONF_EMAIL,
    CONF_EXPIRY,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
    MEDIA_BASE_URL,
    MEDIA_UPLOAD_PREFIX,
    TOKEN_REFRESH_BUFFER,
)
import time

if TYPE_CHECKING:
    from music_assistant_models.config_entries import ProviderConfig
    from music_assistant_models.provider import ProviderManifest

    from music_assistant.mass import MusicAssistant
    from music_assistant.models import ProviderInstanceType

API_URL = "https://jewishmusic.fm:8443/graphql"


async def setup(
    mass: MusicAssistant, manifest: ProviderManifest, config: ProviderConfig
) -> ProviderInstanceType:
    """Initialize provider(instance) with given configuration."""
    if not config.get_value(CONF_REFRESH_TOKEN):
        raise LoginFailed("Sign in with your Zing email and password to set up this provider")
    return ZingProvider(mass, manifest, config)


async def store_auth_data(
    mass: MusicAssistant, instance_id: str, auth_data: dict[str, Any]
) -> None:
    """Persist normalized Firebase auth data for a provider instance."""
    expiry = time.time() + int(auth_data["expires_in"])
    mass.config.set_raw_provider_config_value(
        instance_id, CONF_USER_ID, str(auth_data["user_id"])
    )
    mass.config.set_raw_provider_config_value(
        instance_id, CONF_ACCESS_TOKEN, str(auth_data["access_token"]), encrypted=True
    )
    mass.config.set_raw_provider_config_value(
        instance_id, CONF_REFRESH_TOKEN, str(auth_data["refresh_token"]), encrypted=True
    )
    mass.config.set_raw_provider_config_value(instance_id, CONF_EXPIRY, str(expiry))


def _apply_auth_data(
    values: dict[str, ConfigValueType], auth_data: dict[str, Any]
) -> None:
    values[CONF_REFRESH_TOKEN] = auth_data["refresh_token"]
    values[CONF_ACCESS_TOKEN] = auth_data["access_token"]
    values[CONF_USER_ID] = auth_data["user_id"]
    values[CONF_EXPIRY] = str(time.time() + auth_data["expires_in"])
    values[CONF_PASSWORD] = None


async def _handle_auth_actions(
    mass: MusicAssistant,
    action: str | None,
    values: dict[str, ConfigValueType] | None,
    instance_id: str | None,
) -> None:
    """Handle login / clear-auth actions from the config flow."""
    if values is None:
        return

    if action == CONF_ACTION_LOGIN:
        email = str(values.get(CONF_EMAIL) or "")
        password = str(values.get(CONF_PASSWORD) or "")
        auth_data = await ZingAuthHelper.login_with_email_password(email, password)
        _apply_auth_data(values, auth_data)
        if instance_id and not instance_id.startswith("zing--"):
            await store_auth_data(mass, instance_id, auth_data)

    elif action == CONF_ACTION_CLEAR_AUTH:
        values[CONF_EMAIL] = None
        values[CONF_PASSWORD] = None
        values[CONF_REFRESH_TOKEN] = None
        values[CONF_ACCESS_TOKEN] = None
        values[CONF_USER_ID] = None
        values[CONF_EXPIRY] = None


async def get_config_entries(
    mass: MusicAssistant,
    instance_id: str | None = None,
    action: str | None = None,
    values: dict[str, ConfigValueType] | None = None,
) -> tuple[ConfigEntry, ...]:
    """Return config entries for the Zing provider setup flow."""
    assert values is not None
    await _handle_auth_actions(mass, action, values, instance_id)

    refresh_token = values.get(CONF_REFRESH_TOKEN)
    authenticated = refresh_token not in (None, "")

    if authenticated:
        intro_label = (
            "Signed in to Zing Music. Click Save if you changed settings, or Sign out "
            "to use a different account."
        )
    else:
        intro_label = (
            "Enter the same email and password you use at zingmusic.app, then click Sign in."
        )

    entries: list[ConfigEntry] = [
        ConfigEntry(
            key="auth_intro",
            type=ConfigEntryType.LABEL,
            label=intro_label,
        ),
        ConfigEntry(
            key=CONF_EMAIL,
            type=ConfigEntryType.STRING,
            label="Email",
            description="Your Zing Music account email",
            required=not authenticated,
            value=str(values.get(CONF_EMAIL) or ""),
            hidden=authenticated,
        ),
        ConfigEntry(
            key=CONF_PASSWORD,
            type=ConfigEntryType.SECURE_STRING,
            label="Password",
            description="Your Zing Music account password",
            required=not authenticated,
            value=str(values.get(CONF_PASSWORD) or ""),
            hidden=authenticated,
        ),
        ConfigEntry(
            key=CONF_REFRESH_TOKEN,
            type=ConfigEntryType.SECURE_STRING,
            label=CONF_REFRESH_TOKEN,
            hidden=True,
            required=True,
            value=values.get(CONF_REFRESH_TOKEN, ""),
        ),
        ConfigEntry(
            key=CONF_ACCESS_TOKEN,
            type=ConfigEntryType.SECURE_STRING,
            label=CONF_ACCESS_TOKEN,
            hidden=True,
            value=values.get(CONF_ACCESS_TOKEN, ""),
        ),
        ConfigEntry(
            key=CONF_USER_ID,
            type=ConfigEntryType.STRING,
            label=CONF_USER_ID,
            hidden=True,
            value=values.get(CONF_USER_ID, ""),
        ),
        ConfigEntry(
            key=CONF_EXPIRY,
            type=ConfigEntryType.STRING,
            label=CONF_EXPIRY,
            hidden=True,
            value=values.get(CONF_EXPIRY, ""),
        ),
    ]

    if not authenticated:
        entries.append(
            ConfigEntry(
                key=CONF_ACTION_LOGIN,
                type=ConfigEntryType.ACTION,
                label="Sign in",
                description="Sign in to Zing Music with your email and password.",
                action=CONF_ACTION_LOGIN,
                depends_on=CONF_EMAIL,
            )
        )
    else:
        entries.append(
            ConfigEntry(
                key=CONF_ACTION_CLEAR_AUTH,
                type=ConfigEntryType.ACTION,
                label="Sign out",
                description="Remove stored Zing credentials.",
                action=CONF_ACTION_CLEAR_AUTH,
                action_label="Sign out",
            )
        )

    return tuple(entries)


class ZingProvider(MusicProvider):
    """Support for the Zing GraphQL music provider."""

    api_url: str = API_URL

    @property
    def supported_features(self) -> set[ProviderFeature]:
        """Return the features supported by this provider."""
        return {
            ProviderFeature.SEARCH,
            ProviderFeature.LIBRARY_ARTISTS,
            ProviderFeature.LIBRARY_ALBUMS,
            ProviderFeature.LIBRARY_TRACKS,
            ProviderFeature.LIBRARY_PLAYLISTS,
            ProviderFeature.ARTIST_ALBUMS,
            ProviderFeature.ARTIST_TOPTRACKS,
            ProviderFeature.AUDIO_SOURCE,  # Enable streaming support
            ProviderFeature.BROWSE,        # Add BROWSE support
            ProviderFeature.LIBRARY_RADIOS,        # Add radio support
            ProviderFeature.LIBRARY_RADIOS_EDIT,
        }

    def _config_str(self, key: str) -> str:
        """Read a decrypted config value (required for SECURE_STRING fields)."""
        val = self.config.get_value(key)
        return str(val) if val is not None else ""

    def _sync_auth_to_config(self, auth_data: dict[str, Any]) -> None:
        """Keep in-memory provider config aligned after token refresh."""
        expiry = str(time.time() + int(auth_data["expires_in"]))
        if CONF_USER_ID in self.config.values:
            self.config.values[CONF_USER_ID].value = str(auth_data["user_id"])
        if CONF_ACCESS_TOKEN in self.config.values:
            self.config.values[CONF_ACCESS_TOKEN].value = self.mass.config.encrypt_string(
                str(auth_data["access_token"])
            )
        if CONF_REFRESH_TOKEN in self.config.values:
            self.config.values[CONF_REFRESH_TOKEN].value = self.mass.config.encrypt_string(
                str(auth_data["refresh_token"])
            )
        if CONF_EXPIRY in self.config.values:
            self.config.values[CONF_EXPIRY].value = expiry

    @property
    def user_id(self) -> str:
        val = self._config_str(CONF_USER_ID)
        if not val:
            self.logger.warning("user_id is not set in provider config")
        return val

    @property
    def token(self) -> str:
        return self._config_str(CONF_ACCESS_TOKEN)

    @property
    def refresh_token(self) -> str:
        return self._config_str(CONF_REFRESH_TOKEN)

    @property
    def expiry(self) -> str:
        return self._config_str(CONF_EXPIRY)

    def _track_file_path(self, data: dict[str, Any]) -> str | None:
        """Extract audio file path from GraphQL track payload."""
        file_path = data.get("file") or data.get("fileName")
        if not file_path:
            return None
        return str(file_path).strip()

    def _build_audio_url(self, file_path: str) -> str:
        """Build the jewishmusic.fm URL for a track audio file."""
        path = file_path.strip()
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path.startswith("/"):
            path = f"/{path}"
        if not path.startswith(MEDIA_UPLOAD_PREFIX):
            path = f"{MEDIA_UPLOAD_PREFIX}{path}"
        return f"{MEDIA_BASE_URL}{path}"

    def _content_type_for_path(self, file_path: str) -> ContentType:
        """Guess content type from the file extension."""
        lower = file_path.lower()
        if lower.endswith((".m4a", ".mp4")):
            return ContentType.M4A
        if lower.endswith(".flac"):
            return ContentType.FLAC
        if lower.endswith(".ogg"):
            return ContentType.OGG
        return ContentType.MP3

    def _stream_headers(self) -> dict[str, str]:
        """Headers required by the Zing CDN (same as zingmusic.app)."""
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; MusicAssistant/1.0)",
            "Referer": "https://zingmusic.app/",
            "Origin": "https://zingmusic.app",
        }
        token = self.token
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _graphql(self, query: str, variables: dict[str, Any] | None = None) -> Any:
        """Perform a GraphQL request."""
        variables = variables or {}

        try:
            request_data = {"query": query, "variables": variables}
            headers = {"Content-Type": "application/json"}

            # Inline token logic since _get_valid_token is removed
            access_token = self.token
            expiry = int(float(self.expiry)) if self.expiry else 0


            if (
                not access_token
                or not expiry
                or time.time() > (expiry - TOKEN_REFRESH_BUFFER)
            ):
                self.logger.debug("Refreshing Zing access token")
                auth_data = await ZingAuthHelper.login_with_refresh_token(self.refresh_token)
                access_token = auth_data["access_token"]
                await store_auth_data(self.mass, self.instance_id, auth_data)
                self._sync_auth_to_config(auth_data)

            headers["Authorization"] = f"Bearer {access_token}"
            async with self.mass.http_session.post(
                self.api_url, json=request_data, headers=headers
            ) as resp:
                if resp.status != 200:
                    try:
                        error_data = await resp.text()
                    except:
                        pass
                resp.raise_for_status()
                data = await resp.json()
        except ClientResponseError as err:
            self.logger.error(f"GraphQL request failed with status {err.status}: {err}")
            raise ProviderUnavailableError(str(err)) from err
        except Exception as e:
            self.logger.error(f"GraphQL request failed with exception: {e}")
            raise ProviderUnavailableError(str(e)) from e
        if "errors" in data:
            # Check for auth error
            for err in data["errors"]:
                if "Not Authorised" in err.get("message", ""):
                    self.logger.warning("GraphQL auth error: clearing access token and setting expiry to 0.")
                    self.mass.config.set_raw_provider_config_value(
                        self.instance_id, CONF_ACCESS_TOKEN, ""
                    )
                    self.mass.config.set_raw_provider_config_value(self.instance_id, CONF_EXPIRY, "0")
            error_msg = data["errors"][0].get("message", "unknown error")
            self.logger.error(f"GraphQL returned errors: {error_msg}")
            self.logger.error(f"Full GraphQL error data: {data['errors']}")
            raise ProviderUnavailableError(error_msg)
        return data.get("data")


    async def search(
        self, search_query: str, media_types: list[MediaType], limit: int = 50
    ) -> SearchResults:
        """Perform a search on the provider."""
        import json
        
        results = SearchResults()
        
        # Search for tracks
        if MediaType.TRACK in media_types:
            track_query = {
                "query": {
                    "bool": {
                        "should": [
                            {"match": {"enName": search_query}},
                            {"match": {"heName": search_query}}
                        ]
                    }
                },
                "size": max(limit, 100)  # Use at least 100 results
            }
            track_data = await self._graphql(
                "query SearchElastic($index: String!, $query: String!) { searchElastic(index: $index, query: $query) }",
                {"index": "tracks", "query": json.dumps(track_query)}
            )
            if track_data and track_data.get("searchElastic"):
                try:
                    elastic_data = json.loads(track_data["searchElastic"])
                    if "hits" in elastic_data and "hits" in elastic_data["hits"]:
                        tracks = []
                        for hit in elastic_data["hits"]["hits"]:
                            source = hit["_source"]
                            track = self._parse_track_from_elastic(source)
                            if track:
                                tracks.append(track)
                                if len(tracks) >= limit:
                                    break
                        results.tracks = tracks
                except (json.JSONDecodeError, KeyError):
                    pass
        
        # Search for albums
        if MediaType.ALBUM in media_types:
            album_query = {
                "query": {
                    "bool": {
                        "should": [
                            {"match": {"enName": search_query}},
                            {"match": {"heName": search_query}}
                        ]
                    }
                },
                "size": max(limit, 100)  # Use at least 100 results
            }
            album_data = await self._graphql(
                "query SearchElastic($index: String!, $query: String!) { searchElastic(index: $index, query: $query) }",
                {"index": "albums", "query": json.dumps(album_query)}
            )
            if album_data and album_data.get("searchElastic"):
                try:
                    elastic_data = json.loads(album_data["searchElastic"])
                    if "hits" in elastic_data and "hits" in elastic_data["hits"]:
                        albums = []
                        for hit in elastic_data["hits"]["hits"]:
                            source = hit["_source"]
                            album = self._parse_album_from_elastic(source)
                            if album:
                                albums.append(album)
                                if len(albums) >= limit:
                                    break
                        results.albums = albums
                except (json.JSONDecodeError, KeyError):
                    pass
        
        # Search for artists
        if MediaType.ARTIST in media_types:
            artist_query = {
                "query": {
                    "bool": {
                        "should": [
                            {"match": {"enName": search_query}},
                            {"match": {"heName": search_query}}
                        ]
                    }
                },
                "size": max(limit, 100)  # Use at least 100 results
            }
            artist_data = await self._graphql(
                "query SearchElastic($index: String!, $query: String!) { searchElastic(index: $index, query: $query) }",
                {"index": "artists", "query": json.dumps(artist_query)}
            )
            if artist_data and artist_data.get("searchElastic"):
                try:
                    elastic_data = json.loads(artist_data["searchElastic"])
                    if "hits" in elastic_data and "hits" in elastic_data["hits"]:
                        artists = []
                        for hit in elastic_data["hits"]["hits"]:
                            source = hit["_source"]
                            artist = self._parse_artist_from_elastic(source)
                            if artist:
                                artists.append(artist)
                                if len(artists) >= limit:
                                    break
                        results.artists = artists
                except (json.JSONDecodeError, KeyError):
                    pass
        
        return results

    async def get_track(self, prov_track_id: str) -> Track:
        """Return full track details."""
        self.logger.info(f"Getting track details for ID: {prov_track_id}")
        try:
            query = """
            query GetTrackById($trackId: Int!) {
                track(where: { id: $trackId }) {
                    id
                    trackNumber
                    enName
                    heName
                    file
                    duration
                    album {
                        id
                        enName
                        heName
                        images {
                            small
                            medium
                            large
                        }
                    }
                    artists {
                        id
                        enName
                        heName
                        images {
                            small
                            medium
                            large
                        }
                    }
                    genres {
                        id
                        enName
                        heName
                    }
                    images
                }
            }
            """
            variables = {"trackId": int(prov_track_id)}
            self.logger.debug(f"GraphQL variables: {variables}")
            
            data = await self._graphql(query, variables)
            track_data = data.get("track") if data else None
            
            if not track_data:
                self.logger.error(f"Track {prov_track_id} not found in API response")
                self.logger.debug(f"API response data: {data}")
                raise ProviderUnavailableError(f"Track {prov_track_id} not found")
            
            self.logger.info(f"Successfully retrieved track data for ID: {prov_track_id}")
            return self._parse_track(track_data)
            
        except Exception as e:
            self.logger.error(f"Error getting track {prov_track_id}: {e}")
            raise ProviderUnavailableError(f"Failed to get track {prov_track_id}: {e}")

    async def get_stream_details(self, item_id: str, media_type: MediaType) -> StreamDetails:
        """Return the content details for the given track or radio when it will be streamed."""
        if media_type == MediaType.RADIO:
            radio = await self.get_radio(item_id)
            stream_url = None
            for mapping in radio.provider_mappings:
                if mapping.details:
                    stream_url = mapping.details
                    break
            if not stream_url:
                raise ProviderUnavailableError(f"No stream URL found for radio {item_id}")
            return StreamDetails(
                provider=self.instance_id,
                item_id=radio.item_id,
                audio_format=AudioFormat(content_type=ContentType.MP3),
                stream_type=StreamType.HTTP,
                path=stream_url,
                can_seek=False,
                allow_seek=False,
            )

        track = await self.get_track(item_id)
        file_path = None
        for mapping in track.provider_mappings:
            if mapping.details:
                file_path = str(mapping.details)
                break
        if not file_path:
            raise ProviderUnavailableError(f"No audio file path found for track {item_id}")

        audio_url = self._build_audio_url(file_path)
        content_type = self._content_type_for_path(file_path)
        self.logger.debug("Stream URL for track %s: %s", item_id, audio_url)

        stream_details = StreamDetails(
            provider=self.instance_id,
            item_id=track.item_id,
            audio_format=AudioFormat(content_type=content_type),
            stream_type=StreamType.CUSTOM,
            path=audio_url,
            duration=track.duration,
            can_seek=True,
            allow_seek=True,
        )
        # Content-Length helps Music Assistant with seeking and duration estimates.
        try:
            async with self.mass.http_session.head(
                audio_url, headers=self._stream_headers()
            ) as head_resp:
                if size := head_resp.headers.get("Content-Length"):
                    stream_details.size = int(size)
        except Exception as err:
            self.logger.debug("Could not probe audio file size: %s", err)

        return stream_details

    async def get_audio_stream(
        self, streamdetails: StreamDetails, seek_position: int = 0
    ) -> AsyncGenerator[bytes, None]:
        """Stream track audio with the headers Zing's CDN expects."""
        if not streamdetails.path:
            raise ProviderUnavailableError("No audio path available")

        headers = self._stream_headers()
        # Music Assistant passes seek_position in seconds (not bytes).
        if seek_position > 0 and streamdetails.duration:
            if not streamdetails.size:
                try:
                    async with self.mass.http_session.head(
                        streamdetails.path, headers=headers
                    ) as head_resp:
                        if size := head_resp.headers.get("Content-Length"):
                            streamdetails.size = int(size)
                except Exception:
                    pass
            if streamdetails.size:
                skip_bytes = int(streamdetails.size / streamdetails.duration * seek_position)
                headers["Range"] = f"bytes={skip_bytes}-"

        try:
            async with self.mass.http_session.get(
                streamdetails.path,
                headers=headers,
            ) as response:
                if response.status not in (200, 206):
                    body = await response.text()
                    raise ProviderUnavailableError(
                        f"Audio request failed ({response.status}): {body[:200]}"
                    )
                async for chunk in response.content.iter_chunked(32768):
                    yield chunk
        except ProviderUnavailableError:
            raise
        except Exception as err:
            raise ProviderUnavailableError(f"Failed to stream audio: {err}") from err


    # Library queries
    async def get_library_artists(self) -> AsyncGenerator[Artist, None]:
        if not self.user_id:
            self.logger.info("No user_id set; not fetching library artists.")
            return
        # Fetch user favorites using GetUserMyMusic query
        query = """
        query GetUserMyMusic($userUid: String!) {
          user(where: {uid: $userUid}) {
            myArtists(orderBy: {artistPosition: asc}) {
              artist {
                id
                enName
                heName
                images { small medium large }
              }
            }
          }
        }
        """
        variables = {"userUid": self.user_id}
        try:
            data = await self._graphql(query, variables)
            artists_data = data["user"]["myArtists"]
            for item in artists_data:
                try:
                    artist = self._parse_artist(item["artist"])
                    yield artist
                except Exception as e:
                    self.logger.error(f"Error parsing artist: {e}")
                    continue
        except Exception as e:
            self.logger.error(f"Error fetching user library artists: {e}")
            raise

    async def get_library_albums(self) -> AsyncGenerator[Album, None]:
        if not self.user_id:
            self.logger.info("No user_id set; not fetching library albums.")
            return
        # Fetch user favorites using GetUserMyMusic query
        query = """
        query GetUserMyMusic($userUid: String!) {
          user(where: {uid: $userUid}) {
            myAlbums(orderBy: {albumPosition: asc}) {
              album {
                id
                enName
                heName
                releasedAt
                genres { id enName heName }
                images { small medium large }
                artists { id enName heName images { small medium large } }
              }
            }
          }
        }
        """
        variables = {"userUid": self.user_id}
        try:
            data = await self._graphql(query, variables)
            albums_data = data["user"]["myAlbums"]
            for item in albums_data:
                try:
                    album = self._parse_album(item["album"])
                    yield album
                except Exception as e:
                    self.logger.error(f"Error parsing album: {e}")
                    continue
        except Exception as e:
            self.logger.error(f"Error fetching user library albums: {e}")
            raise

    async def get_library_tracks(self) -> AsyncGenerator[Track, None]:
        if not self.user_id:
            self.logger.info("No user_id set; not fetching library tracks.")
            return
        # Fetch user favorites using GetUserMyMusic query
        query = """
        query GetUserMyMusic($userUid: String!) {
          user(where: {uid: $userUid}) {
            myTracks(orderBy: {trackPosition: asc}) {
              track {
                id
                enName
                heName
                file
                fileName
                duration
                artists {
                    id
                    images { small medium large }

                }
                album {
                  id
                  images { small medium large }
                }
              }
            }
          }
        }
        """
        variables = {"userUid": self.user_id}
        try:
            data = await self._graphql(query, variables)
            tracks_data = data["user"]["myTracks"]
            for item in tracks_data:
                try:
                    track = self._parse_track(item["track"])
                    yield track
                except Exception as e:
                    self.logger.error(f"Error parsing track: {e}")
                    continue
        except Exception as e:
            self.logger.error(f"Error fetching user library tracks: {e}")
            raise

    async def get_library_playlists(self) -> AsyncGenerator[Playlist, None]:
        if not self.user_id:
            self.logger.info("No user_id set; not fetching library playlists.")
            return
        query = '''
        query GetPlaylist($userUid: String!) {
          playlists(
            where: { user: { uid: { equals: $userUid } } }
            orderBy: { index: { sort: asc } }
          ) {
            id
            name
            image
          }
        }
        '''
        variables = {"userUid": self.user_id}
        try:
            data = await self._graphql(query, variables)
            playlists_data = data["playlists"]
            for item in playlists_data:
                try:
                    playlist = self._parse_playlist(item)
                    yield playlist
                except Exception as e:
                    self.logger.error(f"Error parsing playlist: {e}")
                    continue
        except Exception as e:
            self.logger.error(f"Error fetching user playlists: {e}")
            raise

    async def get_library_radios(self) -> AsyncGenerator[Radio, None]:
        """Retrieve all radio stations from the library."""
        query = '''
        query GetRadios($count: Int!) {
          channels(take: $count) {
            id
            enName
            heName
            images
            url
          }
        }
        '''
        variables = {"count": 100}
        try:
            data = await self._graphql(query, variables)
            radios_data = data.get("channels", [])
            for item in radios_data:
                try:
                    radio = self._parse_radio(item)
                    yield radio
                except Exception as e:
                    self.logger.error(f"Error parsing radio: {e}")
                    continue
        except Exception as e:
            self.logger.error(f"Error fetching radios: {e}")
            raise

    async def get_radio(self, prov_radio_id: str) -> Radio:
        """Return radio station details by id."""
        query = '''
        query GetRadio($id: Int!) {
          channel(where: {id: $id}) {
            id
            enName
            heName
            images
            url
          }
        }
        '''
        variables = {"id": int(prov_radio_id)}
        data = await self._graphql(query, variables)
        radio_data = data.get("channel") if data else None
        if not radio_data:
            raise ProviderUnavailableError(f"Radio {prov_radio_id} not found")
        return self._parse_radio(radio_data)

    #Artists
    async def get_artist(self, prov_artist_id: str) -> Artist:
        """Return full artist details."""
        if prov_artist_id == "unknown":
            # Return a default artist for unknown cases
            return Artist(
                item_id="unknown",
                provider=self.instance_id,
                name="Unknown Artist",
                provider_mappings={
                    ProviderMapping(
                        item_id="unknown",
                        provider_domain=self.domain,
                        provider_instance=self.instance_id,
                    )
                },
            )
        
        query = """
        query GetArtist($where: ArtistWhereUniqueInput!) { 
            artist(where: $where) { id enName heName } 
        }
        """
        data = await self._graphql(query, {"where": {"id": int(prov_artist_id)}})
        artist_data = data.get("artist") if data else None
        if not artist_data:
            raise ProviderUnavailableError(f"Artist {prov_artist_id} not found")
        return self._parse_artist(artist_data)

    async def get_artist_albums(self, prov_artist_id: str) -> list[Album]:
        """Return albums for the given artist."""
        if prov_artist_id == "unknown":
            # Return empty list for unknown artist
            return []
        
        query = """
        query GetArtistAlbums($where: ArtistWhereUniqueInput!) {
            artist(where: $where) {
                albums { id enName heName artists { id enName heName images { small medium large } } }
            }
        }
        """
        data = await self._graphql(query, {"where": {"id": int(prov_artist_id)}})
        artist = data.get("artist") if data else None
        if not artist:
            return []
        return [self._parse_album(item) for item in artist.get("albums", [])]

    async def get_artist_toptracks(self, prov_artist_id: str) -> list[Track]:
        """Return top tracks for the given artist."""
        if prov_artist_id == "unknown":
            # Return empty list for unknown artist
            return []
        
        query = """
        query GetArtistTop($where: ArtistWhereUniqueInput!) {
            artist(where: $where) {
                tracks { id enName heName duration file album { id enName heName images { small medium large } } artists { id enName heName images { small medium large } } }
            }
        }
        """
        data = await self._graphql(query, {"where": {"id": int(prov_artist_id)}})
        artist = data.get("artist") if data else None
        if not artist:
            return []
        return [self._parse_track(item) for item in artist.get("tracks", [])]

    #Albums
    async def get_album(self, prov_album_id: str) -> Album:
        """Return full album details."""
        query = """
        query GetAlbum($where: AlbumWhereUniqueInput!) { 
            album(where: $where) { id enName heName images { small medium large } artists { id enName heName images { small medium large } } } 
        }
        """
        data = await self._graphql(query, {"where": {"id": int(prov_album_id)}})
        album_data = data.get("album") if data else None
        if not album_data:
            raise ProviderUnavailableError(f"Album {prov_album_id} not found")
        return self._parse_album(album_data)

    async def get_album_tracks(self, prov_album_id: str) -> list[Track]:
        """Return the tracks for the given album."""
        query = """
        query GetAlbum($where: AlbumWhereUniqueInput!) {
            album(where: $where) {
                tracks {
                    id
                    enName
                    heName
                    duration
                    file
                    artists { id enName heName }
                    album { id enName heName images { small medium large } }
                }
            }
        }
        """
        data = await self._graphql(query, {"where": {"id": int(prov_album_id)}})
        album = data.get("album") if data else None
        if not album:
            return []
        return [self._parse_track(item) for item in album.get("tracks", [])]

    #Playlists
    async def get_playlist(self, prov_playlist_id: str) -> Playlist:
        """Return full playlist details."""
        query = """
        query GetPlaylist($where: PlaylistWhereUniqueInput!) { 
            playlist(where: $where) { id enName heName } 
        }
        """
        data = await self._graphql(query, {"where": {"id": int(prov_playlist_id)}})
        playlist_data = data.get("playlist") if data else None
        if not playlist_data:
            raise ProviderUnavailableError(f"Playlist {prov_playlist_id} not found")
        return self._parse_playlist(playlist_data)

    async def get_playlist_tracks(self, prov_playlist_id: str, page: int = 0, page_size: int = 100) -> list[Track]:
        """Return the tracks for the given playlist."""
        if page > 0:
            return []
        query = """
        query GetPlaylistTracks($playlistId: Int!) {
            playlist(where: { id: $playlistId }) {
                playlistTracks(orderBy: { trackPosition: asc }) {
                    track {
                        id
                        enName
                        heName
                        file
                        duration
                        album { id enName heName images { small medium large } }
                        artists { id enName heName images { small medium large } }
                    }
                }
            }
        }
        """
        variables = {"playlistId": int(prov_playlist_id)}
        data = await self._graphql(query, variables)
        playlist = data.get("playlist") if data else None
        if not playlist:
            return []
        tracks = []
        for item in playlist.get("playlistTracks", []):
            track_data = item.get("track")
            if track_data:
                track = self._parse_track(track_data)
                tracks.append(track)
        return tracks

    #Radios
    async def get_similar_tracks(self, prov_track_id: str, limit: int = 25) -> list[Track]:
        """Retrieve tracks similar to the provided track."""
        # Similar tracks functionality not available in this API
        return []

    # parsers for playlists and radios
    def _parse_playlist(self, data: dict[str, Any]) -> Playlist:
        # Parse playlist as before, but do not assign tracks (linter error)
        playlist = Playlist(
            item_id=str(data["id"]),
            provider=self.instance_id,
            name=data.get("name") or data.get("heName") or data.get("enName") or "Unknown Playlist",
            provider_mappings={
                ProviderMapping(
                    item_id=str(data["id"]),
                    provider_domain=self.domain,
                    provider_instance=self.instance_id,
                )
            },
        )
        image_url = data.get("image")
        if image_url:
            from music_assistant_models.media_items import MediaItemImage
            playlist.metadata.images = UniqueList([
                MediaItemImage(
                    type=ImageType.THUMB,
                    path=image_url,
                    provider=self.instance_id,
                )
            ])
        return playlist

    def _parse_radio(self, data: dict[str, Any]) -> Radio:
        from music_assistant_models.media_items import MediaItemImage
        images = data.get("images")
        image_url = None
        if isinstance(images, list) and images:
            image_url = images[0]
        elif isinstance(images, dict):
            image_url = images.get("large") or images.get("medium") or images.get("small")
        elif isinstance(images, str) and images:
            image_url = images
        radio = Radio(
            item_id=str(data["id"]),
            provider=self.instance_id,
            name=data.get("heName") or data.get("enName") or "Unknown Radio",
            provider_mappings={
                ProviderMapping(
                    item_id=str(data["id"]),
                    provider_domain=self.domain,
                    provider_instance=self.instance_id,
                    details=data.get("url"),
                )
            },
        )
        if image_url:
            radio.metadata.images = UniqueList([
                MediaItemImage(
                    type=ImageType.THUMB,
                    path=image_url,
                    provider=self.instance_id,
                )
            ])
        return radio

    def _parse_artist(self, data: dict[str, Any]) -> Artist:
        artist_name = data.get("heName") or data.get("enName") or "Unknown Artist"
        artist = Artist(
            item_id=str(data["id"]),
            provider=self.instance_id,
            name=artist_name,
            provider_mappings={
                ProviderMapping(
                    item_id=str(data["id"]),
                    provider_domain=self.domain,
                    provider_instance=self.instance_id,
                )
            },
        )
        if images_data := data.get("images"):
            from music_assistant_models.media_items import MediaItemImage
            image_url = images_data.get("large") or images_data.get("medium") or images_data.get("small")
            if image_url:
                self.logger.debug(f"Adding image to artist {artist_name}: {image_url}")
                artist.metadata.images = UniqueList([
                    MediaItemImage(
                        type=ImageType.THUMB,
                        path=image_url,
                        provider=self.instance_id,
                    )
                ])
            else:
                self.logger.debug(f"No valid image URL found for artist {artist_name}")
        else:
            self.logger.debug(f"No images data found for artist {artist_name}")
        return artist

    def _parse_album(self, data: dict[str, Any]) -> Album:
        artists_data = data.get("artists", [])
        if not artists_data:
            # Create a default "heName" if no artists are provided
            # Music Assistant requires albums to have at least one artist
            artists = [
                Artist(
                    item_id="unknown",
                    provider=self.instance_id,
                    name="heName",
                    provider_mappings={
                        ProviderMapping(
                            item_id="unknown",
                            provider_domain=self.domain,
                            provider_instance=self.instance_id,
                        )
                    },
                )
            ]
        else:
            artists = [self._parse_artist(art) for art in artists_data]
        
        album = Album(
            item_id=str(data["id"]),
            provider=self.instance_id,
            name=data.get("heName") or data.get("enName") or "Unknown Album",
            artists=UniqueList(artists),
            provider_mappings={
                ProviderMapping(
                    item_id=str(data["id"]),
                    provider_domain=self.domain,
                    provider_instance=self.instance_id,
                )
            },
        )
        if images_data := data.get("images"):
            from music_assistant_models.media_items import MediaItemImage
            image_url = images_data.get("large") or images_data.get("medium") or images_data.get("small")
            if image_url:
                self.logger.debug(f"Adding image to album {data.get('heName') or data.get('enName')}: {image_url}")
                album.metadata.images = UniqueList([
                    MediaItemImage(
                        type=ImageType.THUMB,
                        path=image_url,
                        provider=self.instance_id,
                    )
                ])
            else:
                self.logger.debug(f"No valid image URL found in images data for album {data.get('heName') or data.get('enName')}")
                self.logger.debug(f"Images data structure: {images_data}")
        else:
            self.logger.debug(f"No images data found for album {data.get('heName') or data.get('enName')}")
        return album

    def _parse_track(self, data: dict[str, Any]) -> Track:
        track_name = data.get("heName") or data.get("enName") or "Unknown Track"
        file_path = self._track_file_path(data)
        
        # Log track parsing details
        self.logger.debug(f"Parsing track: {track_name} (ID: {data.get('id')})")
        if file_path:
            self.logger.debug(f"Track {track_name} has audio file: {file_path}")
        else:
            self.logger.warning(f"Track {track_name} has no audio file path")
        
        artists = [self._parse_artist(art) for art in data.get("artists", [])]
        album = self._parse_album(data["album"]) if data.get("album") else None

        image_url = None
        if album and getattr(album, "image", None):
             image_url = getattr(album.image, "path", None)


           
        track = Track(
            item_id=str(data["id"]),
            provider=self.instance_id,
            name=track_name,
            duration=int(data.get("duration") or 0),
            artists=UniqueList(artists),
            album=album,
            provider_mappings={
                ProviderMapping(
                    item_id=str(data["id"]),
                    provider_domain=self.domain,
                    provider_instance=self.instance_id,
                    details=file_path,  # Store the file path for streaming
                )
            },
        )
        
        # Set track images with priority: 1) track's own image, 2) album image, 3) artist image
        track_image_set = False
        
        if image_url:
            from music_assistant_models.media_items import MediaItemImage
            track.metadata.images = UniqueList([
                MediaItemImage(
                    type=ImageType.THUMB,
                    path=image_url,
                    provider=self.instance_id,
                )
            ])
            
        return track

    def _parse_track_from_elastic(self, data: dict[str, Any]) -> Track | None:
        """Parse track data from Elasticsearch response."""
        try:
            artists = [self._parse_artist(art) for art in data.get("artists", [])]
            album = self._parse_album_from_elastic(data["album"]) if data.get("album") else None
            track = Track(
                item_id=str(data["id"]),
                provider=self.instance_id,
                name=data.get("heName") or data.get("enName") or "Unknown Track",
                duration=int(data.get("duration") or 0),
                artists=UniqueList(artists),
                album=album,
                provider_mappings={
                    ProviderMapping(
                        item_id=str(data["id"]),
                        provider_domain=self.domain,
                        provider_instance=self.instance_id,
                        details=self._track_file_path(data),
                    )
                },
            )
            
            # Set track images with priority: 1) track's own image, 2) album image, 3) artist image
            track_image_set = False
            track_name = data.get('heName') or data.get('enName') or "Unknown Track"
            
            # 1. Try track's own image first
            if track and track.image:
                self.logger.debug(f"Using album image for track {track_name}")
                track_image_set = True
            
            # 2. Fallback to album image
            if not track_image_set and album and album.metadata.images:
                track.metadata.images = album.metadata.images
                self.logger.debug(f"Using album image for track {track_name}")
                track_image_set = True
            
            # 3. Fallback to artist image
            if not track_image_set and artists and artists[0].metadata.images:
                track.metadata.images = artists[0].metadata.images
                self.logger.debug(f"Using artist image for track {track_name}")
                track_image_set = True
            
            if not track_image_set:
                self.logger.debug(f"No image available for track {track_name}")
            
            return track
        except (KeyError, ValueError):
            return None

    def _parse_album_from_elastic(self, data: dict[str, Any]) -> Album | None:
        """Parse album data from Elasticsearch response."""
        try:
            artists_data = data.get("artists", [])
            if not artists_data:
                # Create a default "heName" if no artists are provided
                # Music Assistant requires albums to have at least one artist
                artists = [
                    Artist(
                        item_id="unknown",
                        provider=self.instance_id,
                        name="heName",
                        provider_mappings={
                            ProviderMapping(
                                item_id="unknown",
                                provider_domain=self.domain,
                                provider_instance=self.instance_id,
                            )
                        },
                    )
                ]
            else:
                artists = [self._parse_artist(art) for art in artists_data]
            
            album = Album(
                item_id=str(data["id"]),
                provider=self.instance_id,
                name=data.get("heName") or data.get("enName") or "Unknown Album",
                artists=UniqueList(artists),
                provider_mappings={
                    ProviderMapping(
                        item_id=str(data["id"]),
                        provider_domain=self.domain,
                        provider_instance=self.instance_id,
                    )
                },
            )
            if image_url := data.get("thumbnail"):
                from music_assistant_models.media_items import MediaItemImage
                if image_url:
                    album.metadata.images = UniqueList([
                        MediaItemImage(
                            type=ImageType.THUMB,
                            path=image_url,
                            provider=self.instance_id,
                        )
                    ])
            return album
        except (KeyError, ValueError):
            return None

    def _parse_artist_from_elastic(self, data: dict[str, Any]) -> Artist | None:
        """Parse artist data from Elasticsearch response."""
        try:
            artist = Artist(
                item_id=str(data["id"]),
                provider=self.instance_id,
                name=data.get("heName") or data.get("enName") or "Unknown Artist",
                provider_mappings={
                    ProviderMapping(
                        item_id=str(data["id"]),
                        provider_domain=self.domain,
                        provider_instance=self.instance_id,
                    )
                },
            )
            if image_url := data.get("thumbnail"):
                from music_assistant_models.media_items import MediaItemImage
                if image_url:
                    artist.metadata.images = UniqueList([
                        MediaItemImage(
                            type=ImageType.THUMB,
                            path=image_url,
                            provider=self.instance_id,
                        )
                    ])
            return artist
        except (KeyError, ValueError):
            return None

   