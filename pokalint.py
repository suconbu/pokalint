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
        if type(pattern) is str:
            pattern_string = pattern
            message = None
        else:
            pattern_string = pattern["pattern"]
            message = pattern["message"]
        match = re.match(r"/(.*)/(\w)?", pattern_string)
        if match:
            flags = 0
            if match.group(2) and "i" in match.group(2):
                flags |= re.I
            self.pattern = re.compile(match.group(1), flags)
            self.regex = True
        else:
            self.pattern = pattern_string
            self.regex = False
        self.message = message

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

class Inspector(object):
    def __init__(self, setting_path):
        setting_root = json.load(open(setting_path))
        self.inspect_patterns_by_category = self.__get_patterns_from_setting(setting_root["inspect"])
        self.current_filename = ""
        self.current_lineno = 0
        self.report = None

    def __get_patterns_from_setting(self, setting_group):
        patterns = {}
        for category in setting_group.keys():
            patterns[category] = list(map(lambda p: Pattern(p), setting_group[category]))
        return patterns

    def inspect(self, lines):
        self.report = Report(self.inspect_patterns_by_category.keys())
        filename_pattern = re.compile(r"^\+\+\+ (?:b/)?(.+)$")
        lineno_pattern = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)")
        add_count = 0
        remove_count = 0
        for line in lines:
            if line.startswith("---"):
                pass
            elif line.startswith("+++"):
                self.current_filename = filename_pattern.match(line).group(1)
                self.report.change_file_count += 1
            elif line.startswith("@@"):
                self.current_lineno = int(lineno_pattern.match(line).group(1))
                add_count = 0
                remove_count = 0
            else:
                if line.startswith("-"):
                    remove_count += 1
                    #self.report.remove_line_count += 1
                elif line.startswith("+"):
                    add_count += 1
                    self.__inspect_line(line[1:].rstrip("\n"))
                else:
                    if 0 < add_count:
                        if remove_count <= add_count:
                            self.report.modify_line_count += remove_count
                            self.report.add_line_count += (add_count - remove_count)
                        elif add_count < remove_count:
                            self.report.modify_line_count += add_count
                            self.report.remove_line_count += (remove_count - add_count)
                    elif 0 < remove_count:
                        self.report.remove_line_count += remove_count
                    add_count = 0
                    remove_count = 0
                self.current_lineno += 1
        return self.report

    def __inspect_line(self, line):
        for category in self.inspect_patterns_by_category:
            for pattern in self.inspect_patterns_by_category[category]:
                position = pattern.match(line)
                if position:
                    entry = Entry()
                    entry.filename = self.current_filename
                    entry.lineno = self.current_lineno
                    entry.start = position[0]
                    entry.end = position[1]
                    entry.text = line.replace("\t", " ")
                    entry.pattern = pattern
                    self.report.add_entry(category, entry)

class Report(object):
    def __init__(self, categories):
        self.entries_by_category = {}
        for category in categories:
            self.entries_by_category[category] = []
        self.change_file_count = 0
        self.add_line_count = 0
        self.remove_line_count = 0
        self.modify_line_count = 0

    def add_entry(self, category, entry):
        self.entries_by_category[category].append(entry)

    def output(self):
        self.output_detail()
        print("-" * 40 + "\n")
        self.output_summary()

    def output_detail(self):
        for category in self.entries_by_category:
            entries = self.entries_by_category[category]
            count = len(entries)
            s = "# {0} - {1}".format(category, count)
            if count == 0:
                print(concolor.green(s))
            else:
                print(concolor.red(s))
            print()
            for entry in entries:
                print("{0}:{1}".format(entry.filename, entry.lineno))
                print(entry.text)
                width_start = len_on_screen(entry.text[:entry.start])
                width_match = len_on_screen(entry.text[entry.start:entry.end])
                print(" " * width_start + "^" * width_match)
                if entry.pattern.message:
                    match_word = entry.text[entry.start:entry.end]
                    print(entry.pattern.message.replace("{0}", match_word))
                print()

    def output_summary(self):
        print("# SUMMARY")
        print()
        self.output_statistics()
        self.output_inspection()

    def output_statistics(self):
        print("## Statistics")
        print()
        print("* Change file  - {0:5} files".format(self.change_file_count))
        print("* Total modify - {0:5} lines".format(self.modify_line_count))
        print("* Total add    - {0:5} lines".format(self.add_line_count))
        print("* Total remove - {0:5} lines".format(self.remove_line_count))
        print()

    def output_inspection(self):
        print("## Inspection")
        print()
        max_width = len_on_screen(max(self.entries_by_category, key = lambda entry : len(entry)))
        label = "Category"
        for category in self.entries_by_category:
            entries = self.entries_by_category[category]
            count = len(entries)
            s = "* {0}{1} - {2:3}".format(category, " " * (max_width - len_on_screen(category)), count)
            if count == 0:
                print(concolor.green(s))
            else:
                print(concolor.red(s))
        print()

class Entry(object):
    pass

def main(argv):
    if 1 < len(argv):
        setting_file = argv[1]
    else:
        setting_file = os.path.join(os.path.dirname(__file__), "pokalint_setting.json")
    inspector = Inspector(setting_file)
    report = inspector.inspect(sys.stdin.readlines())
    report.output()

if __name__ == "__main__":
    main(sys.argv)
