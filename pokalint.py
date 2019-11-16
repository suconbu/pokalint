#!/usr/bin/env python3

import os
import sys
import re
import json

class Context(object):
    def __init__(self):
        self.filename = None
        self.lineno = 0

class Pattern(object):
    '''
    Regex or string pattern object
    '''
    def __init__(self, pattern):
        match = re.match(r"/(.*)/(\w)?", pattern)
        if match:
            flags = 0
            if match.group(2) and "i" in match.group(2):
                flags |= re.I
            self.pattern = re.compile(match.group(1), flags)
            self.regex = True
        else:
            self.pattern = pattern
            self.regex = False
    def match(self, s):
        position = None
        if self.regex:
            match = self.pattern.search(s)
            if match:
                position = (match.start(0), match.end(0))
        else:
            index = s.find(self.pattern)
            if 0 <= index:
                position = (index, index + len(self.pattern))
        return position

class Entry(object):
    def __init__(self, filename, lineno, start, end, text):
        self.filename = filename
        self.lineno = lineno
        self.start = start
        self.end = end
        self.text = text

class Color(object):
    def green(s):
        return "\033[32m" + s + "\033[0m"
    def red(s):
        return "\033[31m" + s + "\033[0m"

def load_setting(path):
    setting = json.load(open(path))
    for key in setting:
        patterns = []
        for p in setting[key]:
            patterns.append(Pattern(p))
        setting[key] = patterns
    return setting

def inspect_line(context, line, setting, result):
    for key in setting:
        for pattern in setting[key]:
            position = pattern.match(line)
            if position:
                result[key].append(Entry(context.filename, context.lineno, position[0], position[1], line.replace("\t", " ")))

def inspect_lines(lines, setting, result):
    context = Context()
    filename_pattern = re.compile(r"^\+\+\+ b/(.+)$")
    lineno_pattern = re.compile(r"^@@ -\d+,\d+ \+(\d+),\d+ @@")
    for line in lines:
        if line.startswith("+++"):
            context.filename = filename_pattern.match(line).group(1)
        elif line.startswith("@@"):
            context.lineno = int(lineno_pattern.match(line).group(1))
        else:
            if line.startswith("+"):
                inspect_line(context, line[1:].rstrip("\n"), setting, result)
            context.lineno += 1

def new_result(setting):
    result = {}
    for key in setting:
        result[key] = []
    return result

def output_result(result):
    for key in result:
        count = len(result[key])
        message = "# " + key + " - "
        if count == 0:
            print(Color.green(message + "OK"))
        else:
            print(Color.red(message + "NOK:" + str(count)))
        print()
        for entry in result[key]:
            print("{0}:{1}".format(entry.filename, entry.lineno))
            print(entry.text)
            print(" " * entry.start + "^" * (entry.end - entry.start))
            print()

def main(argv):
    if 1 < len(argv):
        setting_file = argv[1]
    else:
        setting_file = os.path.join(os.path.dirname(__file__), "pokalint_setting.json")
    setting = load_setting(setting_file)
    
    result = new_result(setting)
    inspect_lines(sys.stdin.readlines(), setting, result)
    output_result(result)

if __name__ == "__main__":
    main(sys.argv)
