#!/usr/bin/env python3

import os
import re
import sys
import json
import datetime
import concolor
import unicodedata
from collections import OrderedDict

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

    def match_any(patterns, s):
        for pattern in patterns:
            position = pattern.match(s)
            if position:
                return position
        return None

class Inspector(object):
    def __init__(self, setting_path):
        setting_root = json.load(open(setting_path), object_pairs_hook = OrderedDict)
        self.exclude_path_patterns = self.__get_patterns(setting_root["exclude-path-patterns"])
        self.counter_patterns_by_category = self.__get_patterns_by_category(setting_root["counter"])
        self.warning_patterns_by_category = self.__get_patterns_by_category(setting_root["warning"])
        self.current_filename = ""
        self.current_lineno = 0
        self.report = None

    def __get_patterns_by_category(self, categories):
        patterns = OrderedDict()
        for category in categories.keys():
            patterns[category] = self.__get_patterns(categories[category])
        return patterns

    def __get_patterns(self, array):
        return list(map(Pattern, array))

    def inspect(self, lines):
        self.report = Report(
            self.counter_patterns_by_category.keys(),
            self.warning_patterns_by_category.keys())
        filename_pattern = re.compile(r"^\+\+\+ (?:b/)?(.+)$")
        lineno_pattern = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)")
        add_count = 0
        delete_count = 0
        for line in lines:
            if line.startswith("---"):
                pass
            elif line.startswith("+++"):
                filename = filename_pattern.match(line).group(1)
                if Pattern.match_any(self.exclude_path_patterns, filename):
                    self.current_filename = None
                else:
                    self.current_filename = filename_pattern.match(line).group(1)
                self.report.changed_file_count += 1
            elif line.startswith("@@"):
                add_count = 0
                self.current_lineno = int(lineno_pattern.match(line).group(1))
                delete_count = 0
            else:
                if line.startswith("-"):
                    delete_count += 1
                elif line.startswith("+"):
                    add_count += 1
                    if self.current_filename:
                        self.__inspect_line(line[1:].rstrip("\n"))
                else:
                    if 0 < add_count:
                        if delete_count == 0:
                            self.report.pure_added_line_count += add_count
                            self.report.added_block_count += 1
                        else:
                            self.report.replace_added_line_count += add_count
                            self.report.replace_deleted_line_count += delete_count
                            self.report.replaced_block_count += 1
                    elif 0 < delete_count:
                        self.report.pure_deleted_line_count += delete_count
                        self.report.deleted_block_count += 1
                    add_count = 0
                    delete_count = 0
                self.current_lineno += 1
        return self.report

    def __inspect_line(self, line):
        for category in self.warning_patterns_by_category:
            for pattern in self.warning_patterns_by_category[category]:
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
        for category in self.counter_patterns_by_category:
            for pattern in self.counter_patterns_by_category[category]:
                position = pattern.match(line)
                if position:
                    self.report.increase_count(category)

class Report(object):
    def __init__(self, counter_categories, warning_categories):
        self.counter_by_category = OrderedDict.fromkeys(counter_categories, 0)
        self.entries_by_category = OrderedDict()
        for category in warning_categories:
            self.entries_by_category[category] = []
        self.changed_file_count = 0
        self.pure_added_line_count = 0
        self.pure_deleted_line_count = 0
        self.replace_added_line_count = 0
        self.replace_deleted_line_count = 0
        self.added_block_count = 0
        self.deleted_block_count = 0
        self.replaced_block_count = 0
        self.__styling = False
        self.__indent_level = 0
        self.__newline = True

    def increase_count(self, cateogry):
        self.counter_by_category[cateogry] += 1

    def add_entry(self, cateogry, entry):
        self.entries_by_category[cateogry].append(entry)

    def output(self, styling):
        self.__styling = styling
        self.output_inspection_result()
        self.__print("-" * 40)
        print()
        self.output_statistics()
        self.output_counter()
        self.output_inspection_summary()

    def output_inspection_result(self):
        for category in self.entries_by_category:
            entries = self.entries_by_category[category]
            count = len(entries)
            if 0 < count:
                self.__print("# {0} - {1}".format(category, count), "red")
                self.__print()
                self.__indent()
                for entry in entries:
                    self.__print("{0}:{1}  ".format(entry.filename, entry.lineno), "*")

                    self.__print("```")
                    self.__print(entry.text[:entry.start], "", False)
                    self.__print(entry.text[entry.start:entry.end], "*red", False)
                    self.__print(entry.text[entry.end:])

                    width_start = len_on_screen(entry.text[:entry.start])
                    width_match = len_on_screen(entry.text[entry.start:entry.end])
                    self.__print(" " * width_start + "^" + "~" * (width_match - 1), "*red")
                    if entry.pattern.message:
                        match_word = entry.text[entry.start:entry.end]
                        self.__print(entry.pattern.message.replace("{0}", match_word))
                    self.__print("```")
                    self.__print()
                self.__unindent()

    def output_statistics(self):
        self.__print("# Summary")
        self.__print()
        self.__indent()
        self.__print("* Changed file   - {0:5}".format(self.changed_file_count))
        self.__print("* Block")
        self.__print("  * Add          - {0:5}".format(self.added_block_count))
        self.__print("  * Delete       - {0:5}".format(self.deleted_block_count))
        self.__print("  * Replace      - {0:5}".format(self.replaced_block_count))
        self.__print("* Line")
        self.__print("  * Total add    - {0:5}".format(self.pure_added_line_count + self.replace_added_line_count))
        self.__print("    * Pure       - {0:5}".format(self.pure_added_line_count))
        self.__print("    * Replace    - {0:5}".format(self.replace_added_line_count))
        self.__print("  * Total delete - {0:5}".format(self.pure_deleted_line_count + self.replace_deleted_line_count))
        self.__print("    * Pure       - {0:5}".format(self.pure_deleted_line_count))
        self.__print("    * Replace    - {0:5}".format(self.replace_deleted_line_count))
        self.__unindent()
        self.__unindent()
        self.__print()

    def output_counter(self):
        self.__print("# Counts")
        self.__print()
        self.__indent()
        max_width = len_on_screen(max(self.counter_by_category, key = lambda entry : len(entry)))
        for category in self.counter_by_category:
            count = self.counter_by_category[category]
            self.__print("* {0}{1} - {2:5} {3}".format(
                category, " " * (max_width - len_on_screen(category)),
                count,
                "#" * count))
        self.__unindent()
        self.__print()

    def output_inspection_summary(self):
        self.__print("# Warnings")
        self.__print()
        self.__indent()
        max_width = len_on_screen(max(self.entries_by_category, key = lambda entry : len(entry)))
        for category in self.entries_by_category:
            entries = self.entries_by_category[category]
            count = len(entries)
            self.__print(
                "* {0}{1} - {2:3} {3}".format(category, " " * (max_width - len_on_screen(category)), count, "#" * count),
                "green" if (count == 0) else "red")
        self.__unindent()
        self.__print()


    def write_log(self, log_dir):
        now = datetime.datetime.now()
        log_path = os.path.join(log_dir, "{0:04}W{1:02}".format(now.year, now.isocalendar()[1]) + ".log")
        with open(log_path, "a") as f:
            summary = OrderedDict()
            summary["f"] = self.changed_file_count
            summary["+"] = self.pure_added_line_count + self.replace_added_line_count
            summary["-"] = self.pure_deleted_line_count + self.replace_deleted_line_count
            warnings = OrderedDict()
            for category in self.entries_by_category:
                entries = self.entries_by_category[category]
                warnings[category] = len(entries)
            data = {"summary":summary, "warnings": warnings}
            f.write("{0};{1};{2};\n".format(
                re.sub("[-:]", "", re.sub("\.\d*", "", now.isoformat())),
                os.getcwd(),
                json.dumps(data, separators=(',', ':'), ensure_ascii=False)))

    def __print(self, string = "", style = "", newline = True):
        if self.__styling:
            bold = style.startswith("*")
            color = style[1:] if bold else style
            if color == "red":
                s = concolor.red(string, bold)
            elif color == "green":
                s = concolor.green(string, bold)
            elif color == "cyan":
                s = concolor.cyan(string, bold)
            else:
                s = concolor.default(string, bold)
        else:
            s = string
        print(
            ("  " * self.__indent_level + s) if self.__newline else s,
            end = "\n" if newline else "")
        self.__newline = newline

    def __indent(self):
        self.__indent_level += 1

    def __unindent(self):
        if 0 < self.__indent_level:
            self.__indent_level -= 1

class Entry(object):
    pass

def main(argv):
    app_dir = os.path.dirname(__file__)
    lines = []
    if 1 < len(argv):
        with open(argv[1]) as f:
            lines = f.readlines()
    else:
        lines = sys.stdin.readlines()

    setting_file = os.path.join(app_dir, "pokalint_setting.json")
    inspector = Inspector(setting_file)
    report = inspector.inspect(lines)
    report.output(sys.stdout.isatty())

    log_dir = os.path.join(app_dir, "log")
    if os.path.isdir(log_dir):
        report.write_log(log_dir)

if __name__ == "__main__":
    main(sys.argv)
