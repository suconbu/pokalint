#!/usr/bin/env python3

from pokalint import *

test_diff_files = [
    "./diff_git.txt",
    "./diff_git_bom.txt",
    "./diff_git_sjis.txt",
    "./diff_git_utf16.txt"
]

def test_pattern():
    p = Pattern("hoge")
    assert(p)
    assert(p.match("This is hoge."))
    p = Pattern("/\\bhoge\\b/")
    assert(p.match("This is hoge."))
    assert(not p.match("This is hogeee."))
    p = Pattern("/\\bhoge\\b/i")
    assert(p.match("This is hoge."))
    assert(p.match("This is Hoge."))
    assert(p.match("This is HOGE."))

def test_inspector(capfd):
    i = Inspector("./pokalint_setting.json")
    assert(i)
    with open(test_diff_files[0]) as f:
        i.inspect(f.readlines())
    r = i.report
    assert(r is not None)
    assert(r.added_block_count == 9)
    assert(r.deleted_block_count == 2)
    assert(r.replaced_block_count == 1)
    assert(r.pure_added_line_count == 46)
    assert(r.replace_added_line_count == 1)
    assert(r.pure_deleted_line_count == 3)
    assert(r.replace_deleted_line_count == 1)
    r.output(False)
    o, e = capfd.readouterr()
    verify_output(o, e, [4, 2, 3])

def test_main_stdin(capfd):
    stdin = None
    with open(test_diff_files[0], mode="r", encoding="utf-8") as f:
        stdin = f.readlines()
    main(["pokalint.py"], stdin)
    o, e = capfd.readouterr()
    verify_output(o, e, [4, 2, 3])

def test_main_args1(capfd):
    main(["pokalint.py", test_diff_files[0]])
    o, e = capfd.readouterr()
    verify_output(o, e, [4, 2, 3])

def test_main_args2(capfd):
    main(["pokalint.py"] + test_diff_files)
    o, e = capfd.readouterr()
    verify_output(o, e, [8, 4, 6], skipped=True)

def test_main_args3(capfd):
    main(["pokalint.py", "-v"] + test_diff_files)
    o, e = capfd.readouterr()
    verify_output(o, e, [8, 4, 6], verbose=True, skipped=True)

def test_main_args4(capfd):
    main(["pokalint.py", "notfound.txt"] + test_diff_files)
    o, e = capfd.readouterr()
    verify_output(o, e, [8, 4, 6], skipped=True, notfound=True)

def test_main_args5(capfd):
    main(["pokalint.py", "concolor.py"])
    o, e = capfd.readouterr()
    verify_output(o, e, [1, 0, 0])

def verify_output(o, e, counts, verbose=False, skipped=False, notfound=False):
    if skipped:
        assert("# Skipped" in o)
    else:
        assert("# Skipped" not in o)

    if verbose:
        assert("diff_git.txt" in e)
    else:
        assert(len(e) == 0)

    if notfound:
        assert("File not found" in o)
    else:
        assert("File not found" not in o)

    if 0 < counts[0]:
        assert("if        -    {0} {1}".format(counts[0], "#" * counts[0]) in o)
    if 0 < counts[1]:
        assert("atoi        -    {0} {1}".format(counts[1], "#" * counts[1]) in o)
    if 0 < counts[2]:
        assert("Deprecated -   {0} {1}".format(counts[2], "#" * counts[2]) in o)
