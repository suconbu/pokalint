#!/usr/bin/env python3

import os
import sys
import re
import json
import concolor
import unicodedata

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

def get_string_width(s):
    sw = 0
    for c in s:
        cw = unicodedata.east_asian_width(c)
        sw += 2 if (cw == 'F' or cw == 'W' or cw == "A") else 1
    return sw

def load_setting(path):
    setting = json.load(open(path))
    for key in setting:
        patterns = []
        for p in setting[key]:
            patterns.append(Pattern(p))
        setting[key] = patterns
    return setting

def inspect_line(context, line, setting, report):
    for key in setting:
        for pattern in setting[key]:
            position = pattern.match(line)
            if position:
                report[key].append(Entry(context.filename, context.lineno, position[0], position[1], line.replace("\t", " ")))

def inspect_lines(lines, setting, report):
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
                inspect_line(context, line[1:].rstrip("\n"), setting, report)
            context.lineno += 1

def new_report(setting):
    report = {}
    for key in setting:
        report[key] = []
    return report

def output_report(report):
    for key in report:
        count = len(report[key])
        message = "# " + key + " - "
        if count == 0:
            print(concolor.green(message + "OK"))
        else:
            print(concolor.red(message + "NOK:" + str(count)))
        print()
        for entry in report[key]:
            print("{0}:{1}".format(entry.filename, entry.lineno))
            print(entry.text)
            width_start = get_string_width(entry.text[:entry.start])
            width_match = get_string_width(entry.text[entry.start:entry.end])
            print(" " * width_start + "^" * width_match)
            print()

def main(argv):
    if 1 < len(argv):
        setting_file = argv[1]
    else:
        setting_file = os.path.join(os.path.dirname(__file__), "pokalint_setting.json")
    setting = load_setting(setting_file)
    
    report = new_report(setting)
    inspect_lines(sys.stdin.readlines(), setting, report)
    output_report(report)

if __name__ == "__main__":
    main(sys.argv)
