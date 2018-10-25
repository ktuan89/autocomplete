import sublime, sublime_plugin

from .common.base_listener import BaseViewDeactivatedListener
from .common.utils import get_autocompletion
from .text_processing import *

stored_suggestions = {}

def reactjs_autocompletion(view, prefix, locations):
    return get_autocompletion(view, prefix, locations, stored_suggestions)


class ReactJSNameExpectation(ConditionExpectationBase):
    def canEmpty(self):
        return False
    def condition(self, c):
        return c.isalnum() or c == "_" or c == '.'


class ReactJSViewDeactivedListener(BaseViewDeactivatedListener):
    def get_suggestions(self, str):
        reactjs_name_rules = [
            OneOfStringsMatchExpectation([" = React.createClass"]).loop(),
            BeginOfLineExpectation(),
            ReactJSNameExpectation().save(),
        ]
        suggestions = scan_text(str, reactjs_name_rules)
        return [s[0] for s in suggestions]

    def suggestion_storage(self):
        global stored_suggestions
        return stored_suggestions
