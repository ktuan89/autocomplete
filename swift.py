import sublime, sublime_plugin

import re
import threading
import time

from os import listdir
from os.path import isfile, join, expanduser
import codecs

class Segment:
    def __init__(self, start, end):
        self.start = start
        self.end = end

    def invalid(self):
        return self.start == -1

    @staticmethod
    def notFound(first_non_scanned):
        return Segment(-1, first_non_scanned)

class ExpectationBase:

    is_looping = False
    is_nested = False
    is_save = False
    transform_expectations = []

    def loop(self):
        self.is_looping = True
        return self

    def nested(self):
        self.is_nested = True
        return self

    def save(self):
        self.is_save = True
        return self

    def transform(self, transform_expectations):
        self.transform_expectations = transform_expectations
        return self

    def scan(self, str, segment):
        pass

class BackwardExpectation(ExpectationBase):
    def __init__(self, count):
        self.count = count

    def scan(self, str, segment):
        return Segment(segment.start, segment.start - self.count)

class OrExpectation(ExpectationBase):
    def __init__(self, exp1, exp2):
        self.exp1 = exp1
        self.exp2 = exp2

    def scan(self, str, segment):
        res = self.exp1.scan(str, segment)
        if res.invalid():
            return self.exp2.scan(str, segment)
        return res

class OffsetExpectation(ExpectationBase):
    def __init__(self, exp, offset):
        self.exp = exp
        self.offset = offset

    def scan(self, str, segment):
        res = self.exp.scan(str, segment)
        if res.invalid():
            return res
        else:
            return Segment(res.start, res.end + self.offset)

class StringMatchExpectation(ExpectationBase):

    def __init__(self, match):
        self.match = match

    def scan(self, str, segment):
        word_len = len(self.match)
        for i in range(segment.start, segment.end):
            if i + word_len <= len(str):
                if str[i : i + word_len] == self.match:
                    return Segment(i, i + word_len)

        return Segment.notFound(segment.end)

class OneOfStringsMatchExpectation(ExpectationBase):

    def __init__(self, matches):
        self.matches = matches

    def scan(self, str, segment):
        for i in range(segment.start, segment.end):
            for word in self.matches:
                word_len = len(word)
                if i + word_len <= len(str):
                    if str[i : i + word_len] == word:
                        return Segment(i, i + word_len)

        return Segment.notFound(segment.end)

class OneOfStringsMatchAtBeginningExpectation(ExpectationBase):

    def __init__(self, matches):
        self.matches = matches

    def scan(self, str, segment):
        for i in range(segment.start, segment.end):
            for word in self.matches:
                word_len = len(word)
                if i + word_len <= len(str):
                    if str[i : i + word_len] == word:
                        return Segment(i, i + word_len)
            break

        return Segment.notFound(segment.start)

class ConditionExpectationBase(ExpectationBase):

    def canEmpty(self):
        return True

    def condition(self, c):
        return False

    def scan(self, str, segment):
        start = segment.start
        i = start
        while i < len(str):
            if not self.condition(str[i]):
                break
            i = i + 1
        if not self.canEmpty() and i == start:
            return Segment.notFound(start)
        return Segment(start, i)

class WordExpectation(ConditionExpectationBase):
    def canEmpty(self):
        return False
    def condition(self, c):
        return c.isalnum() or c == "_"

class SpacesExpectation(ConditionExpectationBase):
    def condition(self, c):
        return c == " " or c == "\t" or c == "\n"

class AtLeastOneSpacesExpectation(ConditionExpectationBase):
    def canEmpty(self):
        return False
    def condition(self, c):
        return c == " " or c == "\t" or c == "\n"

class GrabUntilExpectation(ConditionExpectationBase):
    def __init__(self, blacklist):
        self.blacklist = blacklist

    def condition(self, c):
        for b in self.blacklist:
            if c == b:
                return False
        return True

class MatchBracketExpectation(ExpectationBase):

    def __init__(self, openBracket, closeBracket):
        self.openBracket = openBracket
        self.closeBracket = closeBracket

    def scan(self, str, segment):
        if str[segment.start] != self.openBracket:
            return Segment.notFound(segment.start)
        count = 1
        i = segment.start + 1
        while i < len(str):
            if str[i] == self.openBracket:
                count = count + 1
            if str[i] == self.closeBracket:
                count = count - 1
            if count < 0:
                return Segment.notFound(i)
            if count == 0:
                return Segment(segment.start, i + 1)
            i = i + 1
        return Segment.notFound(i)

class CapitalizedWordExpectation(ExpectationBase):
    def scan(self, str, segment):
        start = segment.start
        i = start
        while i < len(str):
            condition = (i == start and str[i].isupper()) or (i > start and (str[i].isalnum() or str[i] == "_"))
            if not condition:
                break
            i = i + 1
        if i == start:
            return Segment.notFound(start)
        return Segment(start, i)

def scan_text_recursive(str, segment, expectations, results, current_matches):
    if len(expectations) == 0:
        results.append(current_matches)
        return segment.start
    # print("recursive: ", segment.start, " ", segment.end, " ", expectations[0])

    start = segment.start
    end = segment.end
    expectation = expectations[0]
    is_looping = expectation.is_looping
    is_nested = expectation.is_nested
    is_save = expectation.is_save
    while start < end:
        res = expectation.scan(str, Segment(start, end))
        if res.invalid():
            if is_looping:
                start = res.end
            else:
                return res.end
        else:
            new_matches = current_matches
            if res.start <= res.end and is_save:
                new_matches = current_matches[:]
                if len(expectation.transform_expectations) > 0:
                    new_str = str[res.start : res.end]
                    transform_results = []
                    #print(new_str)
                    #print(expectation.transform_expectations)
                    scan_text_recursive(new_str, Segment(0, len(new_str)), expectation.transform_expectations, transform_results, [])
                    new_matches.append(transform_results)
                else:
                    new_matches.append(str[res.start : res.end])

            if is_nested:
                scan_to = scan_text_recursive(str, Segment(res.start, res.end), expectations[1:], results, new_matches)
            else:
                scan_to = scan_text_recursive(str, Segment(res.end, end), expectations[1:], results, new_matches)

            if is_looping:
                start = max(scan_to, res.end)
            else:
                return max(scan_to, res.end)

    return start

def scan_text(str, expectations):
    results = []
    scan_text_recursive(str, Segment(0, len(str)), expectations, results, [])
    return results

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

suggestions = {}
links = {}

def swift_autocompletion(view, prefix, locations):
    results = []

    word_range = view.word(locations[0] - 2)
    word = view.substr(word_range)

    for view_id, suggestions_per_view in suggestions.items():
        results += filter_suggestion_for_prefix(suggestions_per_view, word)

    results = filter_duplicate(results)

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
    results = []

    word_range = view.word(locations[0] - 2)
    word = view.substr(word_range)

    str = grab_lines(view, word_range.begin())

    word_type = try_to_guess_type(word, str)

    if word_type is not None:
        print("Guess type = ", word_type)
        for view_id, class_to_func in links.items():
            if word_type in class_to_func:
                funcs = class_to_func[word_type]
                for func in funcs:
                    results.append((func + "\t" + "+", func))

    return filter_duplicate(results)

def indentation_heuristic(content):
    indentation = 4
    num_indentation = 1

    arr = content.split("\n")
    stack = []
    results = []
    regex = re.compile("\\b((func\\s+[A-Za-z]+)|(init))\\(.*\\{")

    for s in arr:
        strips = s.strip()
        if strips.startswith("//") or strips == "":
            # ignore comments
            continue
        else:
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

def autocompleteSettings():
    return sublime.load_settings('autocomplete.sublime-settings')

def swiftPreloadFolder():
    return autocompleteSettings().get('preload_swift')

def preload_autocomplete():
    folder = swiftPreloadFolder()
    if folder is not None:
        folder = expanduser(folder)
        onlyfiles = [f for f in listdir(folder) if isfile(join(folder, f))]
        current_id = 123456
        start_time = time.time()
        for file in onlyfiles:
            actual_path = join(folder, file)
            with codecs.open(actual_path, 'r', encoding='utf-8') as f:
                content = f.read()
                suggestions[current_id] = construct_suggestions_swift(content)
                current_id = current_id + 1
        print("Init time = ", time.time() - start_time)
    pass

preload_autocomplete()

class ViewDeactivatedListener(sublime_plugin.EventListener):
    def on_deactivated(self, view):
        print("==============================")
        global suggestions
        global links
        start_time = time.time()
        str = view.substr(sublime.Region(0, view.size()))
        if len(str) >= 200000:
            t = time.time()
            str = indentation_heuristic(str)
            print("Heuristic time = ", time.time() - t)
        else:
            links[view.id()] = construct_links(str)
        suggestions[view.id()] = construct_suggestions_swift(str)
        print("Parse time = ", time.time() - start_time)
