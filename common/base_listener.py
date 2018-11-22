import sublime, sublime_plugin

from .utils import *

import time

class BaseViewDeactivatedListener(sublime_plugin.EventListener):
    def on_deactivated(self, view):
        str = view.substr(sublime.Region(0, view.size()))
        view_id = view.id()

        sublime.set_timeout_async(lambda: self.parse_str_async(str,
            lambda suggestions: self.parse_completion(view_id, suggestions)), 0)

    def parse_str_async(self, str, completion):
        t = time.time()
        str = comment_and_empty_line_remove(str)
        suggestions = []
        if len(str) >= 200000:
            # TODO:
            pass
        else:
            suggestions = self.get_suggestions(str)
        # print("Total parse time = ", time.time() - t)
        sublime.set_timeout(lambda: completion(suggestions), 0)

    def parse_completion(self, view_id, suggestions):
        stored_suggestions = []
        suggestions_set = set()
        for suggestion in suggestions:
            if not suggestion in suggestions_set:
                suggestions_set.add(suggestion)
                stored_suggestions.append(suggestion)
        storage = self.suggestion_storage()
        storage[view_id] = stored_suggestions

    def get_suggestions(self, str):
        # to override
        return []

    def suggestion_storage(self):
        # to override
        return {}
