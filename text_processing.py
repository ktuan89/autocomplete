
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
    # Move back count characters to continue the search
    def __init__(self, count):
        self.count = count

    def scan(self, str, segment):
        return Segment(segment.start, segment.start - self.count)

class BeginOfLineExpectation(ExpectationBase):
    # Move back to the beginning of a line or the entire string
    def scan(self, str, segment):
        i = segment.start - 1
        while i >= 0 and str[i] != '\n':
            i = i - 1
        return Segment(segment.start, i + 1)

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
    # Find the exact match, if fails, move to the end of segment
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
    # Same as StringMatchExpectation but for an array of matches
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

class OneOfStringsMatchReturnBeginningIfFailsExpectation(ExpectationBase):
    # Same as OneOfStringsMatchExpectation. If fails, keep the search at the beginning of a segment
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

class OneOfStringsMatchAtBeginningExpectation(ExpectationBase):
    # Same as OneOfStringsMatchExpectation but matching must happen at the first char
    def __init__(self, matches):
        self.matches = matches

    def scan(self, str, segment):
        i = segment.start
        for word in self.matches:
            word_len = len(word)
            if i + word_len <= len(str):
                if str[i : i + word_len] == word:
                    return Segment(i, i + word_len)

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

class SpacePrefixedWordExpectation(ExpectationBase):
    def scan(self, str, segment):
        start = segment.start
        i = start
        while i < len(str) and str[i] == ' ':
            i = i + 1
        if i == len(str):
            return Segment.notFound(i)
        start = i
        while i < len(str):
            condition = str[i].isalnum() or str[i] == "_"
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
                start = max(res.end, start + 1)
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
