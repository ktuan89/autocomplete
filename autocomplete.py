import sublime_plugin
import sublime

from .all_views import all_views_autocompletion
from .swift import swift_autocompletion

class KtAutoComplete(sublime_plugin.EventListener):
    def on_query_completions(self, view, prefix, locations):
        if view.substr(locations[0] - 1) == "(" and prefix == "":
            return swift_autocompletion(view, prefix, locations)
        return all_views_autocompletion(view, prefix, locations)
