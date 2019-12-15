#!/usr/bin/env python3

import os
import re
import sys
import math
import glob
import json
import argparse
import datetime
import concolor
import unicodedata
from operator import itemgetter
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

    @staticmethod
    def match_any(patterns, s):
        for pattern in patterns:
            position = pattern.match(s)
            if position:
                return position
        return None

class Inspector(object):
    def __init__(self, setting_path):
        setting_root = json.load(open(setting_path), object_pairs_hook = OrderedDict)
        self.__path_patterns = self.__get_patterns(setting_root["path-patterns"])
        self.__counter_patterns_by_category = self.__get_patterns_by_category(setting_root["counter"])
        self.__warning_patterns_by_category = self.__get_patterns_by_category(setting_root["warning"])
        self.__current_filename = ""
        self.__current_lineno = 0
        self.__report = Report(
            self.__counter_patterns_by_category.keys(),
            self.__warning_patterns_by_category.keys())
        self.__funccall_re = re.compile(r"([_A-Za-z][_0-9A-Za-z]*)\s*\(")
        self.__keywords = ["alignas", "alignof", "and", "and_eq", "asm", "atomic_cancel", "atomic_commit", "atomic_noexcept", "auto", "bitand", "bitor", "bool", "break", "case", "catch", "char", "char8_t", "char16_t", "char32_t", "class", "compl", "concept", "const", "consteval", "constexpr", "constinit", "const_cast", "continue", "co_await", "co_return", "co_yield", "decltype", "default", "delete", "do", "double", "dynamic_cast", "else", "enum", "explicit", "export", "extern", "false", "float", "for", "friend", "goto", "if", "inline", "int", "long", "mutable", "namespace", "new", "noexcept", "not", "not_eq", "nullptr", "operator", "or", "or_eq", "private", "protected", "public", "reflexpr", "register", "reinterpret_cast", "requires", "return", "short", "signed", "sizeof", "static", "static_assert", "static_cast", "struct", "switch", "synchronized", "template", "this", "thread_local", "throw", "true", "try", "typedef", "typeid", "typename", "union", "unsigned", "using", "virtual", "void", "volatile", "wchar_t", "while", "xor", "xor_eq"]

    @property
    def report(self):
        return self.__report

    def inspect(self, lines = None, path = None, all_of_file = False):
        if not lines:
            try:
                if not all_of_file or Pattern.match_any(self.__path_patterns, path):
                    with open(path, mode="r", encoding="utf-8") as f:
                        lines = f.readlines()
            except:
                self.report.skippedfiles[os.path.abspath(path)] = sys.exc_info()[1]

        if not lines:
            return False

        if all_of_file:
            self.__inspect_all(lines, path)
        else:
            if self.__is_diff(lines):
                self.__inspect_diff(lines)
            else:
                if path:
                    self.report.skippedfiles[os.path.abspath(path)] = "Cannot be parse as a diff file"
        return True

    def __is_diff(self, lines):
        for i in range(min(3, len(lines) - 1)):
            if lines[i].startswith("--- ") and lines[i + 1].startswith("+++ "):
                return True
        return False

    def __inspect_all(self, lines, path):
        if path:
            self.__report.increase_file_count(os.path.splitext(path)[1])
            self.__current_filename = os.path.abspath(path)
        else:
            self.__current_filename = None
        self.__current_lineno = 1
        for line in lines:
            self.__inspect_line(line.rstrip("\r\n"))
            self.__current_lineno += 1
        self.__report.non_diff_line_count += len(lines)

    def __inspect_diff(self, lines):
        filename_re = re.compile(r"^\+\+\+ +(?:b/)?(.+\.\w+).*")
        lineno_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)")
        add_count = 0
        delete_count = 0
        for line in lines:
            if line.startswith("---"):
                pass
            elif line.startswith("+++"):
                filename = filename_re.match(line).group(1)
                if Pattern.match_any(self.__path_patterns, filename):
                    self.__current_filename = filename_re.match(line).group(1)
                    self.__report.increase_file_count(os.path.splitext(filename)[1])
                else:
                    self.__current_filename = None
            elif line.startswith("@@"):
                add_count = 0
                self.__current_lineno = int(lineno_re.match(line).group(1))
                delete_count = 0
            else:
                if line.startswith("-"):
                    delete_count += 1
                elif line.startswith("+"):
                    add_count += 1
                    if self.__current_filename:
                        self.__inspect_line(line[1:].rstrip("\r\n"))
                else:
                    if 0 < add_count:
                        if delete_count == 0:
                            self.__report.pure_added_line_count += add_count
                            self.__report.added_block_count += 1
                        else:
                            self.__report.replace_added_line_count += add_count
                            self.__report.replace_deleted_line_count += delete_count
                            self.__report.replaced_block_count += 1
                    elif 0 < delete_count:
                        self.__report.pure_deleted_line_count += delete_count
                        self.__report.deleted_block_count += 1
                    add_count = 0
                    delete_count = 0
                self.__current_lineno += 1

    def __inspect_line(self, line):
        for category in self.__warning_patterns_by_category:
            for pattern in self.__warning_patterns_by_category[category]:
                position = pattern.match(line)
                if position:
                    entry = Entry()
                    entry.filename = self.__current_filename
                    entry.lineno = self.__current_lineno
                    entry.start = position[0]
                    entry.end = position[1]
                    entry.text = line.replace("\t", " ")
                    entry.pattern = pattern
                    self.__report.add_entry(category, entry)
        for category in self.__counter_patterns_by_category:
            for pattern in self.__counter_patterns_by_category[category]:
                position = pattern.match(line)
                if position:
                    self.__report.increase_keyword_count(category)
        matches = self.__funccall_re.findall(line)
        if matches:
            for match in matches:
                if not match in self.__keywords:
                    self.__report.increase_funccall_count(match)

    def __get_patterns_by_category(self, categories):
        patterns = OrderedDict()
        for category in categories.keys():
            patterns[category] = self.__get_patterns(categories[category])
        return patterns

    def __get_patterns(self, array):
        return list(map(Pattern, array))

class Report(object):
    def __init__(self, counter_categories, warning_categories):
        self.non_diff_line_count = 0
        self.pure_added_line_count = 0
        self.pure_deleted_line_count = 0
        self.replace_added_line_count = 0
        self.replace_deleted_line_count = 0
        self.added_block_count = 0
        self.deleted_block_count = 0
        self.replaced_block_count = 0
        self.skippedfiles = {}
        self.__file_count_by_extension = {}
        self.__keyword_count_by_category = OrderedDict.fromkeys(counter_categories, 0)
        self.__entries_by_category = OrderedDict()
        for category in warning_categories:
            self.__entries_by_category[category] = []
        self.__funccall_count_by_name = {}
        self.__to_tty = True
        self.__bar_max = 80

    def increase_file_count(self, extension):
        self.__file_count_by_extension[extension] = self.__file_count_by_extension.setdefault(extension, 0) + 1

    def increase_keyword_count(self, cateogry):
        self.__keyword_count_by_category[cateogry] += 1

    def increase_funccall_count(self, name):
        self.__funccall_count_by_name[name] = self.__funccall_count_by_name.setdefault(name, 0) + 1

    def add_entry(self, cateogry, entry):
        self.__entries_by_category[cateogry].append(entry)

    def output(self, to_tty):
        self.__to_tty = to_tty
        self.__print_separator()
        self.__print()
        if 0 < len(self.skippedfiles):
            self.output_skippedfiles()
            self.__print_separator()
            self.__print()
        if self.output_warning_details():
            self.__print_separator()
            self.__print()
        self.output_summary()
        self.output_counts()
        self.output_funccalls()
        self.output_warnings()

    def output_skippedfiles(self):
        self.__print("# Skipped ({0})".format(len(self.skippedfiles)), "red")
        self.__print()
        for file in self.skippedfiles:
            message = self.skippedfiles[file]
            self.__print("  * {0} - {1}".format(file, message))
        self.__print()
        return True

    def output_warning_details(self):
        total_count = 0
        for category in self.__entries_by_category:
            entries = self.__entries_by_category[category]
            count = len(entries)
            if 0 < count:
                self.__print("# {0} ({1})".format(category, count), "cyan")
                self.__print()
                for entry in entries:
                    self.__print("{0}:{1}  ".format(entry.filename, entry.lineno), "*")

                    self.__print("```")
                    self.__print(entry.text[:entry.start], "", False)
                    self.__print(entry.text[entry.start:entry.end], "*red", False)
                    self.__print(entry.text[entry.end:])

                    width_start = len_on_screen(entry.text[:entry.start])
                    width_match = len_on_screen(entry.text[entry.start:entry.end])
                    self.__print(" " * width_start + "^" + "~" * (width_match - 1), "*red")
                    self.__print("```")
                    if entry.pattern.message:
                        match_word = entry.text[entry.start:entry.end]
                        self.__print("* " + entry.pattern.message.replace("{0}", match_word))
                    self.__print()
            total_count += count
        return bool(total_count)

    def output_summary(self):
        self.__print("# Summary", "cyan")
        self.__print()
        self.__to_tty or self.__print("```")

        total_file_count = sum(self.__file_count_by_extension.values())
        self.__print("  * File ({0}):".format(total_file_count))
        for ext in sorted(self.__file_count_by_extension):
            self.__print("    * {0:10} - {1:4} files".format(ext[1:], self.__file_count_by_extension[ext]))

        total_block_count = self.added_block_count + self.deleted_block_count + self.replaced_block_count
        self.__print("  * Diff block ({0}):".format(total_block_count))
        self.__print("    * Add        - {0:4} blocks".format(self.added_block_count))
        self.__print("    * Delete     - {0:4} blocks".format(self.deleted_block_count))
        self.__print("    * Replace    - {0:4} blocks".format(self.replaced_block_count))

        total_added = self.pure_added_line_count + self.replace_added_line_count
        total_deleted = self.pure_deleted_line_count + self.replace_deleted_line_count
        total_line_count = total_added + total_deleted + self.non_diff_line_count
        self.__print("  * Line ({0}):".format(total_line_count))
        self.__print("    * Add        - {0:4} lines (Pure:{1:4} Replace:{2:4})".format(
            total_added,
            self.pure_added_line_count,
            self.replace_added_line_count))
        self.__print("    * Delete     - {0:4} lines (Pure:{1:4} Replace:{2:4})".format(
            total_deleted,
            self.pure_deleted_line_count,
            self.replace_deleted_line_count))
        if 0 < self.non_diff_line_count:
            self.__print("    * -          - {0:4} lines".format(self.non_diff_line_count))

        self.__to_tty or self.__print("```")
        self.__print()
        return True

    def output_counts(self):
        self.__print("# Counts", "cyan")
        self.__print()
        self.__to_tty or self.__print("```")
        max_width = len_on_screen(max(self.__keyword_count_by_category, key = lambda k : len(k)))
        max_count = max(self.__keyword_count_by_category.values())
        bar_scale = 1 / max(1, math.ceil(max_count / self.__bar_max))
        for category in self.__keyword_count_by_category:
            count = self.__keyword_count_by_category[category]
            self.__print("  * {0}{1} - {2:4} {3}".format(
                category, " " * (max_width - len_on_screen(category)),
                count,
                "#" * math.ceil(count * bar_scale)))
        self.__to_tty or self.__print("```")
        self.__print()

    def output_funccalls(self):
        self.__print("# Function calls", "cyan")
        self.__print()
        self.__to_tty or self.__print("```")
        sorted_list = list(self.__funccall_count_by_name.items())
        sorted_list.sort(key = itemgetter(0), reverse = False)
        sorted_list.sort(key = itemgetter(1), reverse = True)
        if 0 < len(sorted_list):
            max_width = len_on_screen(max(self.__funccall_count_by_name, key = lambda k : len(k)))
            max_width = min(30, max_width)
            max_count = max(sorted_list, key = lambda t: t[1])[1]
            bar_scale = 1 / max(1, math.ceil(max_count / self.__bar_max))
            for name, count in sorted_list:
                self.__print("  * {0}{1} - {2:4} {3}".format(
                    name, " " * (max_width - len_on_screen(name)),
                    count,
                    "#" * math.ceil(count * bar_scale)))
        self.__to_tty or self.__print("```")
        self.__print()
        return bool(len(sorted_list))

    def output_warnings(self):
        self.__print("# Warnings", "cyan")
        self.__print()
        self.__to_tty or self.__print("```")
        max_width = len_on_screen(max(self.__entries_by_category, key = lambda k : len(k)))
        for category in self.__entries_by_category:
            entries = self.__entries_by_category[category]
            count = len(entries)
            self.__print(
                "  * {0}{1} - {2:3} {3}".format(category, " " * (max_width - len_on_screen(category)), count, "#" * count),
                "green" if (count == 0) else "red")
        self.__to_tty or self.__print("```")
        self.__print()
        return True

    def write_log(self, log_dir):
        now = datetime.datetime.now()
        log_path = os.path.join(log_dir, "{0:04}W{1:02}".format(now.year, now.isocalendar()[1]) + ".log")
        with open(log_path, "a") as f:

            summary = OrderedDict()
            summary["f"] = sum(self.__file_count_by_extension.values())
            summary["+"] = self.pure_added_line_count + self.replace_added_line_count
            summary["-"] = self.pure_deleted_line_count + self.replace_deleted_line_count

            warnings = OrderedDict()
            for category in self.__entries_by_category:
                entries = self.__entries_by_category[category]
                warnings[category] = len(entries)

            data = OrderedDict()
            data["summary"] = summary
            data["warnings"] = warnings

            f.write("{0};{1};{2};\n".format(
                re.sub("[-:]", "", re.sub(r"\.\d*", "", now.isoformat())),
                os.getcwd(),
                json.dumps(data, separators=(',', ':'), ensure_ascii=False)))

    def __print(self, string = "", style = "", newline = True):
        if self.__to_tty:
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
        print(s, end = "\n" if newline else "")

    def __print_separator(self, length = 60):
        self.__print("-" * length)

class Entry(object):
    pass


def print_banner():
    print()
    print(" #####    ####   #    #    ##    #        #   #    #  #####")
    print(" #    #  #    #  #   #    #  #   #        #   ##   #    #  ")
    print(" #    #  #    #  ####    #    #  #        #   # #  #    #  ")
    print(" #####   #    #  #  #    ######  #        #   #  # #    #  ")
    print(" #       #    #  #   #   #    #  #        #   #   ##    #  ")
    print(" #        ####   #    #  #    #  ######   #   #    #    #  ")
    print()

def travarse_files(paths, recursive, func):
    for path in paths:
        if os.path.isfile(path) or not os.path.exists(path):
            func(path)
        else:
            if os.path.isdir(path) and recursive:
                travarse_files(glob.glob(os.path.join(path, "*")), recursive, func)

def inspect_file(inspector, path, print_path, all_of_file):
    if inspector.inspect(path=path, all_of_file=all_of_file) and print_path:
        print(os.path.abspath(path), file=sys.stderr)

def main(argv, stdin = None):
    to_tty = sys.stdout.isatty()

    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("-r", "--recursive", dest="recursive", action="store_true", required=False, default=False)
    ap.add_argument("-v", "--verbose", dest="verbose", action="store_true", required=False, default=False)
    ap.add_argument("-a", "--all", dest="all", action="store_true", required=False, default=False)
    ap.add_argument("--help", action="help")
    ap.add_argument("files", metavar="FILE", nargs="*")
    args = ap.parse_args(args=argv[1:])

    if to_tty:
        print_banner()

    app_dir = os.path.dirname(__file__)
    setting_file = os.path.join(app_dir, "pokalint_setting.json")
    inspector = Inspector(setting_file)
    if stdin:
        inspector.inspect(lines=stdin, all_of_file=args.all)
    else:
        travarse_files(
            args.files,
            args.recursive,
            lambda p: inspect_file(inspector, path=p, print_path=args.verbose, all_of_file=args.all))
        if args.verbose:
            print()
    inspector.report.output(to_tty)

    log_dir = os.path.join(app_dir, "log")
    if os.path.isdir(log_dir):
        inspector.report.write_log(log_dir)

if __name__ == "__main__":
    stdin = sys.stdin.readlines() if not sys.stdin.isatty() else None
    main(sys.argv, stdin)
