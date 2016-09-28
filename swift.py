import sublime, sublime_plugin

from .text_processing import *
from .utilities import *

import re
import threading
import time

from os import listdir
from os.path import isfile, join, expanduser
import codecs

import pickle

def sublime_params_snippet_from_str(params_str, is_func):
    if params_str.isspace() or params_str == "":
        return "()"
    else:
        params = params_str.split(",")
        fill_str = "("
        is_first = True
        current_index = 0
        for param in params:
            current_index = current_index + 1
            match = re.match('\s*(\w+\s+)*(\w+)\s*:', param)


            if not is_first:
                fill_str = fill_str + ", "

            param_name = None
            param_var = None
            if match is not None and len(match.groups()) == 2:
                param_var = match.group(2)
                if match.group(1) is not None:
                    param_name = match.group(1).strip()
                else:
                    param_name = match.group(2)


            if param_name is None or param_var is None:
                fill_str = fill_str + "${0}".format(current_index)
            else:
                if is_first and is_func:
                    fill_str = fill_str + "${{{0}:{1}}}".format(current_index, param_var)
                else:
                    fill_str = fill_str + "{1}: ${{{0}:{2}}}".format(current_index, param_name, param_var)

            if is_first:
                is_first = False

        fill_str = fill_str + ")"
        return fill_str

def construct_suggestions_swift(str):
    results = []

    # functions
    func_rules = [
        StringMatchExpectation("func").loop(),
        SpacesExpectation(),
        WordExpectation().save(),
        SpacesExpectation(),
        MatchBracketExpectation("(", ")").save()
    ]

    start_time = time.time()
    funcs = scan_text(str, func_rules)
    print("Parse time func = ", time.time() - start_time)
    # print(funcs)

    for func in funcs:
        results.append((func[0], func[1]))

    # init methods
    class_inits_rules = [
        StringMatchExpectation("class").loop(),
        SpacesExpectation(),
        WordExpectation().save(),
        StringMatchExpectation("{"),
        BackwardExpectation(1),
        MatchBracketExpectation("{", "}").nested(),
        StringMatchExpectation(" init"),
        SpacesExpectation(),
        MatchBracketExpectation("(", ")").save()
    ]

    struct_inits_rules = [
        StringMatchExpectation("struct").loop(),
        SpacesExpectation(),
        WordExpectation().save(),
        StringMatchExpectation("{"),
        BackwardExpectation(1),
        MatchBracketExpectation("{", "}").save().transform([
            OneOfStringsMatchExpectation(["let", "var"]).loop(),
            SpacesExpectation(),
            WordExpectation().save()
        ]),
    ]

    start_time = time.time()
    class_inits = scan_text(str, class_inits_rules)
    print("Parse time class = ", time.time() - start_time)
    # print(class_inits)
    for class_init in class_inits:
            results.append((class_init[0], class_init[1]))

    suggestions = []

    for result in results:
        func_name, params_str = result
        params_str = params_str[1:-1]
        snippet = sublime_params_snippet_from_str(params_str, func_name[0:1].islower())
        if snippet != "()":
            suggestions.append((func_name, snippet[1:-1]))

    start_time = time.time()
    structs = scan_text(str, struct_inits_rules)
    print("Parse time = ", time.time() - start_time)
    # print(structs)
    for struct in structs:
        func_name = struct[0]
        params = struct[1]
        if len(params) > 0:
            # snippet = "("
            snippet = ""
            is_first = True
            current_index = 0
            for param in params:
                current_index = current_index + 1
                if not is_first:
                    snippet = snippet + ", "
                snippet = snippet + "{1}: ${{{0}}}".format(current_index, param[0])
                if is_first:
                    is_first = False
            # snippet = snippet + ")"
            suggestions.append((func_name, snippet))
    return suggestions

def construct_links(str):
    class_funcs_rules = [
        OneOfStringsMatchExpectation(["class", "protocol"]).loop(),
        SpacesExpectation(),
        WordExpectation().save(),
        StringMatchExpectation("{"),
        BackwardExpectation(1),
        MatchBracketExpectation("{", "}").nested(),
        OneOfStringsMatchExpectation(["func", "var", "let"]).loop(),
        AtLeastOneSpacesExpectation(),
        WordExpectation().save()
    ]
    links = scan_text(str, class_funcs_rules)
    class_to_func = {}
    for link in links:
        if len(link) == 2:
            if link[0] in class_to_func:
                class_to_func[link[0]].append(link[1])
            else:
                class_to_func[link[0]] = [link[1]]

    #print(links)
    #print(class_to_func)
    return class_to_func

def filter_suggestion_for_prefix(suggestions, prefix):
    results = []
    for suggestion in suggestions:
        (name, snippet) = suggestion
        if name.lower().startswith(prefix.lower()):
            results.append((snippet, snippet + ")"))
    return results

def filter_duplicate(suggestions):
    results = []
    s = set()
    for suggestion in suggestions:
        (name, params) = suggestion
        uid = name + params
        if uid not in s:
            results.append(suggestion)
            s.add(uid)
    return results

class InsertBracketCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        cursor = -1
        for sel in self.view.sel():
            if sel.empty():
                cursor = sel.begin()
        if cursor > -1:
            self.view.insert(edit, cursor, ")")
            self.view.sel().clear()
            self.view.sel().add(sublime.Region(cursor, cursor))

METHOD_KEY = 'method'
PARAM_KEY = 'param'

suggestions = {}

def swift_autocompletion(view, prefix, locations):
    results = []

    word_range = view.word(locations[0] - 2)
    word = view.substr(word_range)
    #print("autocompletion ", word)
    global suggestions
    #print(suggestions)
    for view_id, suggestions_per_view in suggestions.items():
        if PARAM_KEY in suggestions_per_view:
            results += filter_suggestion_for_prefix(suggestions_per_view[PARAM_KEY], word)

    results = filter_duplicate(results)

    #print(results)

    if len(results) == 0:
        view.run_command("insert_bracket")
        return results
    print(results)
    return results

previous_guess = {}

def try_to_guess_type(variable, str):
    global previous_guess
    type_rule = [
        StringMatchExpectation(variable).loop(),
        SpacesExpectation(),
        OneOfStringsMatchAtBeginningExpectation(["=", ":"]),
        SpacesExpectation(),
        CapitalizedWordExpectation().save()
    ]

    types = scan_text(str, type_rule)
    print(types)
    if len(types) > 0:
        type = types[len(types) - 1][0]
        previous_guess[variable] = type
        return type
    if variable in previous_guess:
        return previous_guess[variable]
    return None

def grab_lines(view, position):
    results = []
    position = view.line(position).begin() - 1
    while position >= 0 and len(results) <= 30:
        line = view.line(position)
        line_str = view.substr(line)
        if not line_str.strip().startswith("//"):
            results.append(line_str)
        position = line.begin() - 1
    return "\n".join(results[::-1])

def swift_autocompletion_call(view, prefix, locations):
    global suggestions
    results = []

    word_range = view.word(locations[0] - 2)
    word = view.substr(word_range)

    str = grab_lines(view, word_range.begin())

    word_type = try_to_guess_type(word, str)

    if word_type is not None:
        #print("Guess type = ", word_type)
        #print("suggestions = ", suggestions)
        for view_id, suggestions_per_view in suggestions.items():
            if METHOD_KEY in suggestions_per_view:
                method_suggestions = suggestions_per_view[METHOD_KEY]
                if word_type in method_suggestions:
                    funcs = method_suggestions[word_type]
                    for func in funcs:
                        results.append((func + "\t" + "+", func))
    return filter_duplicate(results)

def comment_and_empty_line_remove(content):
    arr = content.split("\n")
    results = []
    for s in arr:
        strips = s.strip()
        if strips.startswith("//") or strips == "":
            pass
        else:
            results.append(s)
    return "\n".join(results)

def indentation_heuristic(content):
    indentation = 4
    num_indentation = 1

    arr = content.split("\n")
    stack = []
    results = []
    regex = re.compile("\\b((func\\s+[A-Za-z]+)|(init))\\(.*\\{")

    for s in arr:
        strips = s.strip()
        cp = 0
        while cp < len(s) and s[cp] == " ":
            cp = cp + 1
        # print(cp)
        while len(stack) > 0 and cp == stack[len(stack) - 1] and strips == "}":
            #print("pop " + str(stack[len(stack) - 1]))
            stack.pop()
        if len(stack) > 0 and cp >= stack[len(stack) - 1] + num_indentation * indentation:
            #print("Ignore " + s)
            continue
        else:
            results.append(s)
            if regex.search(s) is not None:
                # print("append " + str(cp) + " " + s)
                stack.append(cp)
    print(str(len(arr)) + " " + str(len(results)))
    return "\n".join(results)

def preload_autocomplete(folder):
    global suggestions
    print(folder)
    if folder is not None:
        folder = expanduser(folder)
        onlyfiles = [f for f in listdir(folder) if isfile(join(folder, f)) and re.match(r'[a-z_A-Z0-9]+(\.[a-z_A-Z0-9]+)*', f)]
        cached_files = set([f for f in onlyfiles if f.endswith(".cached")])
        onlyfiles = [f for f in onlyfiles if not f.endswith(".cached")]
        current_id = 123456
        start_time = time.time()
        #print(onlyfiles)
        for file in onlyfiles:
            cached_file = file + ".cached"
            if cached_file in cached_files:
                actual_path = join(folder, cached_file)
                thefile = open(actual_path, 'rb')
                this_suggestions = pickle.load(thefile)
                thefile.close()
                suggestions[current_id] = this_suggestions
                current_id = current_id + 1
            else:
                actual_path = join(folder, file)
                with codecs.open(actual_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    content = comment_and_empty_line_remove(content)
                    this_suggestions = {
                        PARAM_KEY: construct_suggestions_swift(content),
                        METHOD_KEY: construct_links(content)
                    }

                    cached_path = join(folder, cached_file)
                    thefile = open(cached_path, 'wb')
                    pickle.dump(this_suggestions, thefile)
                    thefile.close()

                    suggestions[current_id] = this_suggestions
                    current_id = current_id + 1

        print("Init time = ", time.time() - start_time)
    pass

# sublime.set_timeout(lambda: preload_autocomplete(), 500)
wait_for_settings_and_do('autocomplete.sublime-settings', 'preload_swift', lambda folder: preload_autocomplete(folder))

class ViewDeactivatedListener(sublime_plugin.EventListener):
    def on_deactivated(self, view):
        print("==============================")
        global suggestions
        start_time = time.time()
        str = view.substr(sublime.Region(0, view.size()))
        str = comment_and_empty_line_remove(str)
        method_suggestions = None
        if len(str) >= 200000:
            t = time.time()
            str = indentation_heuristic(str)
            print("Heuristic time = ", time.time() - t)
        else:
            method_suggestions = construct_links(str)
        print(suggestions, " ", view.id())
        suggestions[view.id()] = { PARAM_KEY: construct_suggestions_swift(str) }
        if method_suggestions is not None:
            suggestions[view.id()][METHOD_KEY] = method_suggestions
        # print(suggestions[view.id()])
        print("Parse time = ", time.time() - start_time)
