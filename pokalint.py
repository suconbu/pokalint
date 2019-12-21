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

def strlen_on_screen(s):
    sw = 0
    for c in s:
        cw = unicodedata.east_asian_width(c)
        sw += 2 if (cw == 'F' or cw == 'W' or cw == "A") else 1
    return sw

class Output(object):
    def __init__(self, file):
        self.__file = file
    
    def print(self, string="", style="", newline=True):
        if self.__file.isatty():
            bold = style.startswith("*")
            color = style[1:] if bold else style
            s = concolor.get(string, color, bold)
        else:
            s = string
        print(s, end=("\n" if newline else ""), file=self.__file)
    
    def isatty(self):
        return self.__file.isatty()

class Pattern(object):
    def __init__(self, pattern):
        if type(pattern) is str:
            pattern_string = pattern
            message = None
            filters = None
        else:
            pattern_string = pattern.get("pattern")
            message = pattern.get("message")
            filters = pattern.get("only")

        match = re.match(r"/(.*)/(\w)?", pattern_string)

        if match:
            flags = 0
            if match.group(2) and "i" in match.group(2):
                flags |= re.I
            self.__pattern = re.compile(match.group(1), flags)
            self.__regex = True
        else:
            self.__pattern = pattern_string
            self.__regex = False
        self.__message = message
        self.__filters = filters

    @property
    def message(self):
        return self.__message

    def match(self, s, t=None):
        if not self.__filters or (t in self.__filters):
            if self.__regex:
                match = self.__pattern.search(s)
                if match:
                    return {"pattern":self, "start":match.start(0), "end":match.end(0)}
            else:
                index = s.find(self.__pattern)
                if 0 <= index:
                    return {"pattern":self, "start":index, "end":index + len(self.__pattern)}
        return None

class PatternSet(object):
    def __init__(self, name, patterns):
        self.__name = name
        self.__patterns = []
        for pattern in patterns:
            self.__patterns.append(Pattern(pattern))

    def match(self, s, t=None):
        for pattern in self.__patterns:
            match = pattern.match(s, t)
            if match:
                match["name"] = self.__name
                return match
        return None

class PatternGroup:
    def __init__(self, patternsets):
        self.__patternsets = OrderedDict()
        for name in patternsets:
            self.__patternsets[name] = PatternSet(name, patternsets[name])
    
    def names(self):
        return self.__patternsets.keys()

    def match(self, s, t = None):
        for name in self.__patternsets:
            match = self.__patternsets[name].match(s, t)
            if match:
                return match
        return None

class Setting(object):
    def __init__(self, setting_path):
        root = json.load(open(setting_path), object_pairs_hook = OrderedDict)
        self.filter = PatternGroup(root["filter"])
        self.counter = PatternGroup(root["counter"])
        self.warning = PatternGroup(root["warning"])

class Inspector(object):
    def __init__(self, setting):
        self.__setting = setting
        self.__current_filename = None
        self.__current_filetype = None
        self.__current_lineno = 0
        self.__report = Report(self.__setting)
        self.__funccall_re = re.compile(r"([_A-Za-z][_0-9A-Za-z]*)\s*\(")
        self.__keywords = ["alignas", "alignof", "and", "and_eq", "asm", "atomic_cancel", "atomic_commit", "atomic_noexcept", "auto", "bitand", "bitor", "bool", "break", "case", "catch", "char", "char8_t", "char16_t", "char32_t", "class", "compl", "concept", "const", "consteval", "constexpr", "constinit", "const_cast", "continue", "co_await", "co_return", "co_yield", "decltype", "default", "delete", "do", "double", "dynamic_cast", "else", "enum", "explicit", "export", "extern", "false", "float", "for", "friend", "goto", "if", "inline", "int", "long", "mutable", "namespace", "new", "noexcept", "not", "not_eq", "nullptr", "operator", "or", "or_eq", "private", "protected", "public", "reflexpr", "register", "reinterpret_cast", "requires", "return", "short", "signed", "sizeof", "static", "static_assert", "static_cast", "struct", "switch", "synchronized", "template", "this", "thread_local", "throw", "true", "try", "typedef", "typeid", "typename", "union", "unsigned", "using", "virtual", "void", "volatile", "wchar_t", "while", "xor", "xor_eq"]
        funcdef_pattern = r"^\s*(?:const\s+)?[A-Za-z_]\w*\s*(?:\**|\s)\s*(?:const)?\s*(?:\**|\s)\s*\b([A-Za-z_]\w*)\s*\("
        self.__funcdecl_re = re.compile(funcdef_pattern + r".*\)\s*(?:const)?\s*;$")
        self.__funcdef_re = re.compile(funcdef_pattern)

    @property
    def report(self):
        return self.__report

    def inspect_file(self, path):
        with open(path, mode="r", encoding="utf-8") as f:
            lines = f.readlines()
        self.__report.increase_file_count(os.path.splitext(path)[1])
        self.__current_filename = os.path.abspath(path)
        match = self.__setting.filter.match(self.__current_filename)
        self.__current_filetype = match and match["name"]
        self.__current_lineno = 1
        for line in lines:
            self.__inspect_line(line.rstrip("\r\n"))
            self.__current_lineno += 1
        self.__report.non_diff_line_count += len(lines)

    def inspect_diff(self, lines):
        if not self.__is_diff(lines):
            raise Exception("Invalid diff format")
        filename_re = re.compile(r"^\+\+\+ +(?:b/)?(.+\.\w+).*")
        lineno_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)")
        add_count = 0
        delete_count = 0
        for line in lines:
            if line.startswith("---"):
                pass
            elif line.startswith("+++"):
                filename = filename_re.match(line).group(1)
                if self.__setting.filter.match(filename):
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

    def __is_diff(self, lines):
        for i in range(min(3, len(lines) - 1)):
            if lines[i].startswith("--- ") and lines[i + 1].startswith("+++ "):
                return True
        return False

    def __inspect_line(self, line):
        warning_match = self.__setting.warning.match(line, self.__current_filetype)
        if warning_match:
            entry = Entry()
            entry.filename = self.__current_filename
            entry.lineno = self.__current_lineno
            entry.start = warning_match["start"]
            entry.end = warning_match["end"]
            entry.text = line.replace("\t", " ")
            entry.pattern = warning_match["pattern"]
            self.__report.add_entry(warning_match["name"], entry)

        counter_match = self.__setting.counter.match(line, self.__current_filetype)
        if counter_match:
            self.__report.increase_keyword_count(counter_match["name"])

        funcdecl_match = self.__funcdecl_re.match(line)
        if funcdecl_match and funcdecl_match.group(1) not in self.__keywords:
            self.__report.add_funcdecl(funcdecl_match.group(1))
        else:
            funcdef_match = self.__funcdef_re.match(line)
            if funcdef_match and funcdef_match.group(1) not in self.__keywords:
                self.__report.add_funcdef(funcdef_match.group(1))
            else:
                matches = self.__funccall_re.findall(line)
                if matches:
                    for match in matches:
                        if match not in self.__keywords:
                            self.__report.increase_funccall_count(match)

class Report(object):
    def __init__(self, setting):
        self.non_diff_line_count = 0
        self.pure_added_line_count = 0
        self.pure_deleted_line_count = 0
        self.replace_added_line_count = 0
        self.replace_deleted_line_count = 0
        self.added_block_count = 0
        self.deleted_block_count = 0
        self.replaced_block_count = 0
        self.__file_count_by_extension = {}
        self.__keyword_count_by_category = OrderedDict.fromkeys(setting.counter.names(), 0)
        self.__entries_by_category = OrderedDict((n, []) for n in setting.warning.names())
        self.__funccall_count_by_name = {}
        self.__funcdecls = set()
        self.__funcdefs = set()
        self.__bar_max = 80
        self.__output = None

    def increase_file_count(self, extension):
        self.__file_count_by_extension[extension] = self.__file_count_by_extension.setdefault(extension, 0) + 1

    def increase_keyword_count(self, cateogry):
        self.__keyword_count_by_category[cateogry] += 1

    def increase_funccall_count(self, name):
        self.__funccall_count_by_name[name] = self.__funccall_count_by_name.setdefault(name, 0) + 1

    def add_funcdecl(self, name):
        self.__funcdecls.add(name)

    def add_funcdef(self, name):
        self.__funcdefs.add(name)

    def add_entry(self, cateogry, entry):
        self.__entries_by_category[cateogry].append(entry)

    def output(self, output):
        self.__output = output
        if self.__output.isatty():
            self.__output.print("-" * 60)
        self.__output.print()
        if self.output_warning_details():
            self.__output.print("-" * 60)
            self.__output.print()
        self.output_summary()
        self.output_counts()
        self.output_funcdefs()
        self.output_funccalls()
        self.output_warnings()

    def output_warning_details(self):
        total_count = 0
        for category in self.__entries_by_category:
            entries = self.__entries_by_category[category]
            count = len(entries)
            if 0 < count:
                self.__output.print("# {0} ({1})".format(category, count), "cyan")
                self.__output.print()
                for entry in entries:
                    self.__output.print("{0}:{1}  ".format(entry.filename, entry.lineno), "*")

                    self.__output.print("```")
                    self.__output.print(entry.text[:entry.start], "", False)
                    self.__output.print(entry.text[entry.start:entry.end], "*red", False)
                    self.__output.print(entry.text[entry.end:])

                    width_start = strlen_on_screen(entry.text[:entry.start])
                    width_match = strlen_on_screen(entry.text[entry.start:entry.end])
                    self.__output.print(" " * width_start + "^" + "~" * (width_match - 1), "*red")
                    self.__output.print("```")
                    if entry.pattern.message:
                        match_word = entry.text[entry.start:entry.end]
                        self.__output.print("* " + entry.pattern.message.replace("{0}", match_word))
                    self.__output.print()
            total_count += count
        return bool(total_count)

    def output_summary(self):
        self.__output.print("# Summary", "cyan")
        self.__output.print()
        self.__output.isatty() or self.__output.print("```")

        total_file_count = sum(self.__file_count_by_extension.values())
        self.__output.print("  * File ({0}):".format(total_file_count))
        for ext in sorted(self.__file_count_by_extension):
            self.__output.print("    * {0:10} - {1:4} files".format(ext[1:], self.__file_count_by_extension[ext]))

        total_block_count = self.added_block_count + self.deleted_block_count + self.replaced_block_count
        self.__output.print("  * Diff block ({0}):".format(total_block_count))
        self.__output.print("    * Add        - {0:4} blocks".format(self.added_block_count))
        self.__output.print("    * Delete     - {0:4} blocks".format(self.deleted_block_count))
        self.__output.print("    * Replace    - {0:4} blocks".format(self.replaced_block_count))

        total_added = self.pure_added_line_count + self.replace_added_line_count
        total_deleted = self.pure_deleted_line_count + self.replace_deleted_line_count
        total_line_count = total_added + total_deleted + self.non_diff_line_count
        self.__output.print("  * Line ({0}):".format(total_line_count))
        self.__output.print("    * Add        - {0:4} lines (Pure:{1:4} Replace:{2:4})".format(
            total_added,
            self.pure_added_line_count,
            self.replace_added_line_count))
        self.__output.print("    * Delete     - {0:4} lines (Pure:{1:4} Replace:{2:4})".format(
            total_deleted,
            self.pure_deleted_line_count,
            self.replace_deleted_line_count))
        if 0 < self.non_diff_line_count:
            self.__output.print("    * -          - {0:4} lines".format(self.non_diff_line_count))

        self.__output.isatty() or self.__output.print("```")
        self.__output.print()
        return True

    def output_counts(self):
        self.__output.print("# Counts", "cyan")
        self.__output.print()
        self.__output.isatty() or self.__output.print("```")
        max_width = strlen_on_screen(max(self.__keyword_count_by_category, key = lambda k : len(k)))
        max_count = max(self.__keyword_count_by_category.values())
        bar_scale = 1 / max(1, math.ceil(max_count / self.__bar_max))
        for category in self.__keyword_count_by_category:
            count = self.__keyword_count_by_category[category]
            self.__output.print("  * {0}{1} - {2:4} {3}".format(
                category, " " * (max_width - strlen_on_screen(category)),
                count,
                "#" * math.ceil(count * bar_scale)))
        self.__output.isatty() or self.__output.print("```")
        self.__output.print()

    def output_funcdefs(self):
        self.__output.print("# Defined functions", "cyan")
        self.__output.print()
        self.__output.isatty() or self.__output.print("```")
        for name in sorted(self.__funcdefs):
            self.__output.print("  * {0}".format(name))
        self.__output.isatty() or self.__output.print("```")
        self.__output.print()

    def output_funccalls(self):
        self.__output.print("# Function calls", "cyan")
        self.__output.print()
        self.__output.isatty() or self.__output.print("```")
        sorted_list = list(self.__funccall_count_by_name.items())
        sorted_list.sort(key = itemgetter(0), reverse = False)
        sorted_list.sort(key = itemgetter(1), reverse = True)
        if 0 < len(sorted_list):
            max_width = strlen_on_screen(max(self.__funccall_count_by_name, key = lambda k : len(k)))
            max_width = min(30, max_width)
            max_count = max(sorted_list, key = lambda t: t[1])[1]
            bar_scale = 1 / max(1, math.ceil(max_count / self.__bar_max))
            for name, count in sorted_list:
                self.__output.print("  * {0}{1} - {2:4} {3}".format(
                    name, " " * (max_width - strlen_on_screen(name)),
                    count,
                    "#" * math.ceil(count * bar_scale)))
        self.__output.isatty() or self.__output.print("```")
        self.__output.print()
        return bool(len(sorted_list))

    def output_warnings(self):
        self.__output.print("# Warnings", "cyan")
        self.__output.print()
        self.__output.isatty() or self.__output.print("```")
        max_width = strlen_on_screen(max(self.__entries_by_category, key = lambda k : len(k)))
        for category in self.__entries_by_category:
            entries = self.__entries_by_category[category]
            count = len(entries)
            self.__output.print(
                "  * {0}{1} - {2:3} {3}".format(category, " " * (max_width - strlen_on_screen(category)), count, "#" * count),
                "green" if (count == 0) else "red")
        self.__output.isatty() or self.__output.print("```")
        self.__output.print()
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

class Entry(object):
    pass

def print_banner(output):
    output.print()
    output.print(" #####    ####   #    #    ##    #        #   #    #  #####", "cyan")
    output.print(" #    #  #    #  #   #    #  #   #        #   ##   #    #  ", "cyan")
    output.print(" #    #  #    #  ####    #    #  #        #   # #  #    #  ", "cyan")
    output.print(" #####   #    #  #  #    ######  #        #   #  # #    #  ", "cyan")
    output.print(" #       #    #  #   #   #    #  #        #   #   ##    #  ", "cyan")
    output.print(" #        ####   #    #  #    #  ######   #   #    #    #  ", "cyan")
    output.print()

def travarse_files(paths, recursive, handler):
    for path in paths:
        if "*" in path:
            travarse_files(glob.glob(path), recursive, handler)
        elif os.path.isfile(path) or not os.path.exists(path):
            handler(path)
        else:
            if os.path.isdir(path) and recursive:
                travarse_files(glob.glob(os.path.join(path, "*")), recursive, handler)

def main(argv, stdin = None):
    app_dir = os.path.dirname(__file__)
    output = Output(sys.stdout)
    error_output = Output(sys.stderr)

    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("-r", "--recursive", dest="recursive", action="store_true", required=False, default=False)
    ap.add_argument("-v", "--verbose", dest="verbose", action="store_true", required=False, default=False)
    ap.add_argument("--help", action="help")
    ap.add_argument("files", metavar="FILE", nargs="*")
    args = ap.parse_args(args=argv[1:])

    if output.isatty():
        print_banner(output)

    try:
        setting = Setting(os.path.join(app_dir, "pokalint_setting.json"))
        inspector = Inspector(setting)
        if stdin:
            inspector.inspect_diff(stdin)
        else:
            def handler(path):
                abspath = os.path.abspath(path)
                if setting.filter.match(abspath):
                    try:
                        inspector.inspect_file(abspath)
                        if args.verbose:
                            error_output.print(abspath)
                    except:
                        error_output.print("{0} - ERROR: {1}".format(abspath, sys.exc_info()[1]), "red")
            travarse_files(args.files, args.recursive, handler)
        inspector.report.output(output)
    except:
        error_output.print("ERROR: {0}".format(sys.exc_info()[1]), "red")
        return

    log_dir = os.path.join(app_dir, "log")
    if os.path.isdir(log_dir):
        inspector.report.write_log(log_dir)

if __name__ == "__main__":
    stdin = sys.stdin.readlines() if not sys.stdin.isatty() else None
    main(sys.argv, stdin)
