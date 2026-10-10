import logging
import threading
from typing import Any

from cozy.architecture.event_sender import EventSender
from cozy.architecture.singleton import Singleton
from cozy.control.librivox import LibriVox, LibriVoxError

log = logging.getLogger(__name__)


class DiscoverViewModel(EventSender, metaclass=Singleton):
    """View model for LibriVox Discover page."""

    def __init__(self) -> None:
        super().__init__()
        self._librivox = LibriVox()
        self._results: list[dict[str, Any]] = []
        self._is_loading: bool = False
        self._error_message: str = ""

    @property
    def results(self) -> list[dict[str, Any]]:
        return self._results

    @property
    def is_loading(self) -> bool:
        return self._is_loading

    @property
    def error_message(self) -> str:
        return self._error_message

    def search(self, query: str) -> None:
        self._is_loading = True
        self._error_message = ""
        self.emit_event("is_loading")
        self.emit_event("error_message")

        def _worker():
            try:
                books = self._librivox.search_audiobooks(query=query)
                self._results = books
            except LibriVoxError as e:
                self._results = []
                self._error_message = str(e)
            finally:
                self._is_loading = False
                self.emit_event("is_loading")
                self.emit_event("results")
                self.emit_event("error_message")

        thread = threading.Thread(target=_worker, name="LibriVoxSearchThread", daemon=True)
        thread.start()
