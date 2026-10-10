import logging
from typing import Any
import requests

log = logging.getLogger(__name__)

LIBRIVOX_API_URL = "https://librivox.org/api/v1/audiobooks"


class LibriVoxError(Exception):
    """Base exception for LibriVox API errors."""


class LibriVox:
    """Client for querying the LibriVox API."""

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout
        self._session = requests.Session()

    def search_audiobooks(
        self, query: str = "", title: str = "", author: str = "", limit: int = 20, page: int = 0
    ) -> list[dict[str, Any]]:
        """Search audiobooks on LibriVox."""
        params: dict[str, Any] = {"format": "json", "limit": limit}

        if page > 0:
            params["offset"] = page * limit

        if title:
            params["title"] = title
        elif query:
            params["title"] = f"^{query}"

        if author:
            params["author"] = author

        try:
            response = self._session.get(LIBRIVOX_API_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and "books" in data:
                return data["books"]
            return []
        except (requests.RequestException, Exception) as e:
            log.error("LibriVox request failed: %s", e)
            raise LibriVoxError(f"Request failed: {e}") from e
