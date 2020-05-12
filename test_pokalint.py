#!/usr/bin/env python3

import pokalint
import re
import pdb

def test_pattern():
    p = pokalint.Pattern("hoge")
    assert(p)
    assert(p.match("This is hoge."))
    p = pokalint.Pattern("/\\bhoge\\b/")
    assert(p.match("This is hoge."))
    assert(not p.match("This is hogeee."))
    p = pokalint.Pattern("/\\bhoge\\b/i")
    assert(p.match("This is hoge."))
    assert(p.match("This is Hoge."))
    assert(p.match("This is HOGE."))

def test_inspector(capfd):
    settings = pokalint.Settings("./pokalint_settings.json")
    inspector = pokalint.Inspector(settings)
    assert(inspector)
    with open("test/diff_git.txt") as f:
        inspector.inspect_diff(f.readlines())
    r = inspector.report
    assert(r is not None)
    assert(r.added_block_count == 9)
    assert(r.deleted_block_count == 2)
    assert(r.replaced_block_count == 1)
    assert(r.pure_added_line_count == 46)
    assert(r.replace_added_line_count == 1)
    assert(r.pure_deleted_line_count == 3)
    assert(r.replace_deleted_line_count == 1)
    r.output(pokalint.Output(pokalint.sys.stdout))
    o, e = capfd.readouterr()
    verify_output(o, e, [4, 2, 4])

def test_main_stdin1(capfd):
    with open("test/diff_git.txt", mode="r", encoding="utf-8") as f:
        lines = f.readlines()
    pokalint.main(["pokalint.py"], lines)
    o, e = capfd.readouterr()
    verify_output(o, e, [4, 2, 4])

def test_main_stdin2(capfd):
    with open("test/helloworld.c", mode="r", encoding="utf-8") as f:
        lines = f.readlines()
    pokalint.main(["pokalint.py"], lines)
    o, e = capfd.readouterr()
    assert(not o)
    assert("Invalid diff format" in e)

def test_main_args1(capfd):
    pokalint.main(["pokalint.py", "test/helloworld.c"])
    o, e = capfd.readouterr()
    verify_output(o, e, [2, 2, 2])

def test_main_args2(capfd):
    pokalint.main(["pokalint.py", "test/helloworld.cpp"])
    o, e = capfd.readouterr()
    verify_output(o, e, [2, 2, 3])

def test_main_args3(capfd):
    pokalint.main(["pokalint.py", "test/*"])
    o, e = capfd.readouterr()
    verify_output(o, e, [10, 9, 11])

def test_main_args4(capfd):
    pokalint.main(["pokalint.py", "test/*", "-v"])
    o, e = capfd.readouterr()
    verify_output(o, e, [10, 9, 11])

def test_main_args5(capfd):
    pokalint.main(["pokalint.py", "test/notfound.c"])
    o, e = capfd.readouterr()
    verify_output(o, e, [0, 0, 0], notfound=True)

def test_main_args6(capfd):
    pokalint.main(["pokalint.py", "*"])
    o, e = capfd.readouterr()
    verify_output(o, e, [0, 0, 0])

def test_main_args7(capfd):
    pokalint.main(["pokalint.py", "*", "-r"])
    o, e = capfd.readouterr()
    verify_output(o, e, [10, 9, 11])

def verify_output(o, e, counts, verbose=False, notfound=False):
    if verbose:
        assert("diff_git.txt" in e)
    else:
        assert(len(e) == 0 or "ERROR" in e)

    if notfound:
        assert("No such file or directory" in e)
    else:
        assert("No such file or directory" not in e)

    if 0 < counts[0]:
        assert(re.search(r"if +- +{0} {1}".format(counts[0], "#" * counts[0]), o) is not None)
    if 0 < counts[1]:
        assert(re.search(r"printf +- +{0} {1}".format(counts[1], "#" * counts[1]), o) is not None)
    if 0 < counts[2]:
        assert(re.search(r"Deprecated +- +{0} {1}".format(counts[2], "#" * counts[2]), o) is not None)
