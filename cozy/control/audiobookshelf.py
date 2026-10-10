import logging
from typing import Any
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)


class AudiobookshelfError(Exception):
    """Base exception for Audiobookshelf backend errors."""


class AudiobookshelfAuthError(AudiobookshelfError):
    """Raised when authentication fails or token is invalid/expired."""


class AudiobookshelfConnectionError(AudiobookshelfError):
    """Raised when server connection fails."""


class Audiobookshelf:
    """Backend client interface for Audiobookshelf REST API."""

    def __init__(self, host: str = "", token: str | None = None, timeout: int = 10) -> None:
        self._host: str = ""
        self.host = host
        self.token: str | None = token
        self.timeout: int = timeout
        self.user: dict[str, Any] | None = None
        self._session: requests.Session = requests.Session()

    @property
    def host(self) -> str:
        return self._host

    @host.setter
    def host(self, value: str) -> None:
        if not value:
            self._host = ""
            return

        url = value.strip()
        if not url.startswith(("http://", "https://")):
            url = f"http://{url}"

        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        self._host = normalized

    @property
    def is_authenticated(self) -> bool:
        return bool(self.token)

    def _get_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(
        self,
        method: str,
        endpoint: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        if not self._host:
            raise AudiobookshelfConnectionError("Host URL is not configured.")

        url = f"{self._host}/{endpoint.lstrip('/')}"
        headers = self._get_headers()

        try:
            response = self._session.request(
                method=method,
                url=url,
                json=json,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            log.error("Network request failed for Audiobookshelf endpoint %s: %s", endpoint, e)
            raise AudiobookshelfConnectionError(f"Connection failed: {e}") from e

        if response.status_code in (401, 403):
            log.warning("Authentication error (%s) on endpoint %s", response.status_code, endpoint)
            raise AudiobookshelfAuthError(
                f"Authentication failed with status code {response.status_code}"
            )

        if not response.ok:
            log.error(
                "HTTP error %s on endpoint %s: %s", response.status_code, endpoint, response.text
            )
            raise AudiobookshelfError(
                f"API request failed with status code {response.status_code}: {response.text}"
            )

        if response.content:
            try:
                return response.json()
            except ValueError as e:
                log.error("Invalid JSON response from endpoint %s: %s", endpoint, e)
                raise AudiobookshelfError("Invalid JSON response from server") from e

        return None

    def login(self, username: str, password: str) -> dict[str, Any]:
        """Authenticate with the Audiobookshelf server using username and password."""
        payload = {"username": username, "password": password}
        try:
            data = self._request("POST", "/login", json=payload)
        except AudiobookshelfAuthError as e:
            raise AudiobookshelfAuthError("Invalid username or password") from e

        if not isinstance(data, dict):
            raise AudiobookshelfError("Unexpected response format during login")

        user_data = data.get("user", {})
        token = user_data.get("token") or data.get("token")
        if not token:
            raise AudiobookshelfAuthError("Login response missing access token")

        self.token = token
        self.user = user_data
        log.info("Successfully logged in to Audiobookshelf as user %s", username)
        return user_data

    def ping(self) -> bool:
        """Check server connectivity and token validity."""
        if self.token:
            try:
                self._request("GET", "/api/authorize")
                return True
            except AudiobookshelfError:
                pass

        try:
            data = self._request("GET", "/ping")
            return isinstance(data, dict) and data.get("success", False)
        except AudiobookshelfError as e:
            raise AudiobookshelfConnectionError(f"Ping failed: {e}") from e

    def get_libraries(self) -> list[dict[str, Any]]:
        """Fetch all libraries available on the server."""
        data = self._request("GET", "/api/libraries")
        if isinstance(data, dict) and "libraries" in data:
            return data["libraries"]
        if isinstance(data, list):
            return data
        return []

    def get_library_items(
        self, library_id: str, limit: int = 0, page: int = 0
    ) -> list[dict[str, Any]]:
        """Fetch audiobooks/items for a specific library."""
        params: dict[str, Any] = {}
        if limit > 0:
            params["limit"] = limit
        if page > 0:
            params["page"] = page

        endpoint = f"/api/libraries/{library_id}/items"
        data = self._request("GET", endpoint, params=params)

        if isinstance(data, dict) and "results" in data:
            return data["results"]
        if isinstance(data, list):
            return data
        return []

    def get_item(self, item_id: str) -> dict[str, Any]:
        """Get detailed metadata for a single item."""
        data = self._request("GET", f"/api/items/{item_id}")
        if isinstance(data, dict):
            return data
        raise AudiobookshelfError("Unexpected item data format")

    def sync_progress(
        self,
        item_id: str,
        current_time: float,
        duration: float,
        progress: float | None = None,
        is_finished: bool = False,
    ) -> dict[str, Any]:
        """Sync playback progress for a specific item to Audiobookshelf."""
        if progress is None:
            progress = (current_time / duration) if duration > 0 else 0.0

        payload = {
            "currentTime": current_time,
            "duration": duration,
            "progress": max(0.0, min(1.0, progress)),
            "isFinished": is_finished,
        }

        endpoint = f"/api/me/progress/{item_id}"
        data = self._request("POST", endpoint, json=payload)
        return data if isinstance(data, dict) else {}

    def get_cover_url(self, item_id: str) -> str:
        """Construct full URL for item cover image."""
        if not self._host:
            return ""

        url = f"{self._host}/api/items/{item_id}/cover"
        if self.token:
            url += f"?token={self.token}"
        return url

    def get_audio_file_url(self, item_id: str, file_id: str) -> str:
        """Construct streaming URL for a specific audio file of an item."""
        if not self._host:
            return ""

        url = f"{self._host}/api/items/{item_id}/file/{file_id}"
        if self.token:
            url += f"?token={self.token}"
        return url
