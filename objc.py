import sublime, sublime_plugin

from .text_processing import *
from .utilities import *

import re

def construct_func_objc(str):
    lines = str.split('\n')
    func_rules = [
        StringMatchExpectation("- ("),
        BackwardExpectation(1),
        MatchBracketExpectation("(", ")"),
        SpacePrefixedWordExpectation().save().loop(),
        StringMatchExpectation(":"),
        MatchBracketExpectation("(", ")"),
        WordExpectation().save(),
    ]

    interface_rules = [
        StringMatchExpectation("@interface"),
        SpacePrefixedWordExpectation().save()
    ]

    last_interface = None
    results = []
    for line in lines:
        sline = line.strip()

        if sline.find("@interface ") >= 0:
            res = scan_text(sline, interface_rules)
            if len(res) > 0:
                last_interface = res[0][0]
        elif sline.startswith("- (instancetype)") or sline.startswith("- (nullable instancetype)"):
            res = scan_text(sline, func_rules)
            if len(res) > 0 and last_interface is not None:
                current_index = 1
                func_name = res[0][0]
                prefix = "initWith"
                if func_name.startswith(prefix) and len(func_name) > len(prefix):
                    func_name = func_name[len(prefix):]
                    func_name = func_name[:1].lower() + func_name[1:]
                s = "{2}: ${{{0}:{1}}}".format(current_index, res[0][1], func_name)
                for i in range(1, len(res)):
                    current_index = current_index + 1
                    s = s + ", {1}: ${{{0}:{2}}}".format(current_index, res[i][0], res[i][1])
                results.append((last_interface, s))
        elif sline.startswith("- ("):
            res = scan_text(sline, func_rules)
            if len(res) > 0:
                current_index = 1
                func_name = res[0][0]
                s = "${{{0}:{1}}}".format(current_index, res[0][1])
                for i in range(1, len(res)):
                    current_index = current_index + 1
                    s = s + ", {1}: ${{{0}:{2}}}".format(current_index, res[i][0], res[i][1])
                results.append((func_name, s))
    return results
