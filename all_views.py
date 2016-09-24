# Extends Sublime Text autocompletion to find matches in all open
# files. By default, Sublime only considers words from the current file.

import sublime_plugin
import sublime
import re
import time

# limits to prevent bogging down the system
MIN_WORD_SIZE = 4
MAX_WORD_SIZE = 80

MAX_VIEWS = 40
MAX_WORDS_PER_VIEW = 10000
MAX_FIX_TIME_SECS_PER_VIEW = 0.04

kt_active_view_list = []

class ActiveViewsTracker(sublime_plugin.EventListener):

    def on_activated(self, view):
        if kt_active_view_list.count(view.id()) > 0:
            kt_active_view_list.remove(view.id())
        kt_active_view_list.insert(0, view.id())
        if len(kt_active_view_list) > MAX_VIEWS:
            kt_active_view_list.pop()

def all_views_autocompletion(view, prefix, locations):
    global kt_active_view_list
    words = []

    # Limit number of views but always include the active view. This
    # view goes first to prioritize matches close to cursor position.
    other_views = [v for v in sublime.active_window().views() if v.id() != view.id()]
    other_views_in_order = []
    added_view = set()
    # TODO: optimize it
    for ordered_index in kt_active_view_list:
        for cur_view in other_views:
            if cur_view.id() == ordered_index and cur_view.id() not in added_view:
                other_views_in_order.append(cur_view)
                added_view.add(cur_view.id())
    for cur_view in other_views:
        if cur_view.id() not in added_view:
            other_views_in_order.append(cur_view)
            added_view.add(cur_view.id())

    views = [view] + other_views_in_order
    views = views[0:MAX_VIEWS]

    for v in views:
        if len(locations) > 0 and v.id == view.id:
            view_words = v.extract_completions(prefix, locations[0])
        else:
            view_words = v.extract_completions(prefix)
        view_words = filter_words(view_words)
        view_words = fix_truncation(v, view_words)
        words += view_words

    words = without_duplicates(words)
    matches = [(w + "\t.", w.replace('$', '\\$')) for w in words]
    return matches

def filter_words(words):
    words = words[0:MAX_WORDS_PER_VIEW]
    return [w for w in words if MIN_WORD_SIZE <= len(w) <= MAX_WORD_SIZE]

# keeps first instance of every word and retains the original order
# (n^2 but should not be a problem as len(words) <= MAX_VIEWS*MAX_WORDS_PER_VIEW)
def without_duplicates(words):
    result = []
    s = set()
    for w in words:
        if w not in s:
            result.append(w)
            s.add(w)
    return result


# Ugly workaround for truncation bug in Sublime when using view.extract_completions()
# in some types of files.
def fix_truncation(view, words):
    fixed_words = []
    start_time = time.time()

    for i, w in enumerate(words):
        #The word is truncated if and only if it cannot be found with a word boundary before and after

        # this fails to match strings with trailing non-alpha chars, like
        # 'foo?' or 'bar!', which are common for instance in Ruby.
        match = view.find(r'\b' + re.escape(w) + r'\b', 0)
        truncated = is_empty_match(match)
        if truncated:
            #Truncation is always by a single character, so we extend the word by one word character before a word boundary
            extended_words = []
            view.find_all(r'\b' + re.escape(w) + r'\w\b', 0, "$0", extended_words)
            if len(extended_words) > 0:
                fixed_words += extended_words
            else:
                # to compensate for the missing match problem mentioned above, just
                # use the old word if we didn't find any extended matches
                fixed_words.append(w)
        else:
            #Pass through non-truncated words
            fixed_words.append(w)

        # if too much time is spent in here, bail out,
        # and don't bother fixing the remaining words
        if time.time() - start_time > MAX_FIX_TIME_SECS_PER_VIEW:
            return fixed_words + words[i+1:]

    return fixed_words

if sublime.version() >= '3000':
  def is_empty_match(match):
    return match.empty()
else:
  def is_empty_match(match):
    return match is None
