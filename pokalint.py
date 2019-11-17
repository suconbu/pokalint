#!/usr/bin/env python3

import os
import sys
import re
import json
import concolor
import unicodedata

def len_on_screen(s):
    sw = 0
    for c in s:
        cw = unicodedata.east_asian_width(c)
        sw += 2 if (cw == 'F' or cw == 'W' or cw == "A") else 1
    return sw

class Pattern(object):
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

class Inspecter(object):
    def __init__(self, setting_path):
        self.patterns_by_category = {}
        setting_json = json.load(open(setting_path))
        self.categories = setting_json.keys()
        for category in self.categories:
            self.patterns_by_category[category] = list(map(lambda p: Pattern(p), setting_json[category]))
        self.current_filename = ""
        self.current_lineno = 0
        self.report = None

    def inspect(self, lines):
        self.report = Report(self.categories)
        filename_pattern = re.compile(r"^\+\+\+ (?:b/)?(.+)$")
        lineno_pattern = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)")
        for line in lines:
            if line.startswith("+++"):
                self.current_filename = filename_pattern.match(line).group(1)
            elif line.startswith("@@"):
                self.current_lineno = int(lineno_pattern.match(line).group(1))
            else:
                if line.startswith("+"):
                    self.__inspect_line(line[1:].rstrip("\n"))
                    self.report.total_add += 1
                elif line.startswith("-"):
                    self.report.total_remove += 1
                self.current_lineno += 1
        return self.report

    def __inspect_line(self, line):
        for category in self.categories:
            for pattern in self.patterns_by_category[category]:
                position = pattern.match(line)
                if position:
                    entry = Entry()
                    entry.filename = self.current_filename
                    entry.lineno = self.current_lineno
                    entry.start = position[0]
                    entry.end = position[1]
                    entry.text = line.replace("\t", " ")
                    self.report.add_entry(category, entry)

class Report(object):
    def __init__(self, categories):
        self.categories = categories
        self.entries_by_category = {}
        for category in categories:
            self.entries_by_category[category] = []
        self.total_add = 0
        self.total_remove = 0

    def add_entry(self, category, entry):
        self.entries_by_category[category].append(entry)

    def output(self):
        for category in self.categories:
            entries = self.entries_by_category[category]
            count = len(entries)
            s = "# " + category + " - "
            if count == 0:
                print(concolor.green(s + "OK"))
            else:
                print(concolor.red(s + "FAIL " + str(count)))
            print()
            for entry in entries:
                print("{0}:{1}".format(entry.filename, entry.lineno))
                print(entry.text)
                width_start = len_on_screen(entry.text[:entry.start])
                width_match = len_on_screen(entry.text[entry.start:entry.end])
                print(" " * width_start + "^" * width_match)
                print()

class Entry(object):
    pass

def main(argv):
    if 1 < len(argv):
        setting_file = argv[1]
    else:
        setting_file = os.path.join(os.path.dirname(__file__), "pokalint_setting.json")
    inspecter = Inspecter(setting_file)
    report = inspecter.inspect(sys.stdin.readlines())
    report.output()

if __name__ == "__main__":
    main(sys.argv)
