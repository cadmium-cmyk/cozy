import logging
import inject
from gi.repository import Adw, Gtk, GLib

from cozy.view_model.discover_view_model import DiscoverViewModel

log = logging.getLogger("DiscoverView")


@Gtk.Template.from_resource("/com/github/geigi/cozy/ui/discover_page.ui")
class DiscoverPage(Gtk.Box):
    __gtype_name__ = "DiscoverPage"

    search_entry: Gtk.SearchEntry = Gtk.Template.Child()
    stack: Gtk.Stack = Gtk.Template.Child()
    results_box: Gtk.FlowBox = Gtk.Template.Child()

    _view_model: DiscoverViewModel = inject.attr(DiscoverViewModel)

    def __init__(self):
        super().__init__()
        self.search_entry.connect("activate", self._on_search_activate)
        self.search_entry.connect("search-changed", self._on_search_changed)

        self._view_model.bind_to("is_loading", self._on_is_loading_changed)
        self._view_model.bind_to("results", self._on_results_changed)

    def _on_search_activate(self, entry):
        query = entry.get_text().strip()
        if query:
            self._view_model.search(query)

    def _on_search_changed(self, entry):
        query = entry.get_text().strip()
        if not query:
            self.stack.set_visible_child_name("empty")

    def _on_is_loading_changed(self):
        GLib.idle_add(self._update_loading_state)

    def _update_loading_state(self):
        if self._view_model.is_loading:
            self.stack.set_visible_child_name("loading")

    def _on_results_changed(self):
        GLib.idle_add(self._update_results)

    def _update_results(self):
        # Clear existing children
        child = self.results_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.results_box.remove(child)
            child = next_child

        results = self._view_model.results
        if not results:
            self.stack.set_visible_child_name("empty")
            return

        for book in results:
            title = book.get("title", _("Unknown Title"))
            authors = book.get("authors", [])
            author_str = ", ".join(
                f"{a.get('first_name', '')} {a.get('last_name', '')}".strip() for a in authors
            ) or _("Unknown Author")

            card = Adw.ActionRow()
            card.set_title(title)
            card.set_subtitle(author_str)

            self.results_box.append(card)

        self.stack.set_visible_child_name("results")
