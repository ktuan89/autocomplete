import sublime_plugin
import sublime

from .all_views import all_views_autocompletion
from .swift import swift_autocompletion
from .swift import swift_autocompletion_call
from .swift import swift_autocompletion_enum
from .swift import swift_autocompletion_case_enum

class KtAutoComplete(sublime_plugin.EventListener):
    def on_query_completions(self, view, prefix, locations):
        if view.settings().get("kt_autocomplete_disabled"):
            return None
        # if locations[0] >= 6 and view.substr(sublime.Region(locations[0] - 6, locations[0])) == "case ." and prefix == "":
        #     return (swift_autocompletion_case_enum(view, prefix, locations), sublime.INHIBIT_WORD_COMPLETIONS)
        # if locations[0] >= 2 and view.substr(sublime.Region(locations[0] - 2, locations[0])) == " ." and prefix == "":
        #     return (swift_autocompletion_enum(view, prefix, locations), sublime.INHIBIT_WORD_COMPLETIONS)
        # if view.substr(locations[0] - 1) == "(" and prefix == "":
        #     return (swift_autocompletion(view, prefix, locations), sublime.INHIBIT_WORD_COMPLETIONS)
        # if view.substr(locations[0] - 1) == "." and prefix == "":
        #     return (swift_autocompletion_call(view, prefix, locations), sublime.INHIBIT_WORD_COMPLETIONS)
        return (all_views_autocompletion(view, prefix, locations), sublime.INHIBIT_WORD_COMPLETIONS)
