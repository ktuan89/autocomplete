import sublime_plugin
import sublime

from .all_views import all_views_autocompletion
from .swift import swift_autocompletion
from .swift import swift_autocompletion_call

class KtAutoComplete(sublime_plugin.EventListener):
    def on_query_completions(self, view, prefix, locations):
        if view.substr(locations[0] - 1) == "(" and prefix == "":
            return (swift_autocompletion(view, prefix, locations), sublime.INHIBIT_WORD_COMPLETIONS)
        if view.substr(locations[0] - 1) == "." and prefix == "":
            return (swift_autocompletion_call(view, prefix, locations), sublime.INHIBIT_WORD_COMPLETIONS)
        return (all_views_autocompletion(view, prefix, locations), sublime.INHIBIT_WORD_COMPLETIONS)
