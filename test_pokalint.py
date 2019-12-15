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
    verify_output(o, multiply=1)
    assert(not e)

def test_main_stdin(capfd):
    stdin = None
    with open(test_diff_files[0], mode="r", encoding="utf-8") as f:
        stdin = f.readlines()
    main(["pokalint.py"], stdin)
    o, e = capfd.readouterr()
    verify_output(o, multiply=1)
    assert(not e)

def test_main_args1(capfd):
    main(["pokalint.py", test_diff_files[0]])
    o, e = capfd.readouterr()
    verify_output(o, multiply=1)
    assert(not e)

def test_main_args2(capfd):
    main(["pokalint.py"] + test_diff_files)
    o, e = capfd.readouterr()
    verify_output(o, multiply=2, skipped=True)
    assert(not e)

def test_main_args3(capfd):
    main(["pokalint.py", "-v"] + test_diff_files)
    o, e = capfd.readouterr()
    verify_output(o, multiply=2, verbose=True, skipped=True)
    assert(not e)

def test_main_args4(capfd):
    main(["pokalint.py", "notfound.txt"] + test_diff_files)
    o, e = capfd.readouterr()
    verify_output(o, multiply=2, skipped=True, notfound=True)
    assert(not e)

def verify_output(o, multiply, verbose=False, skipped=False, notfound=False):
    if skipped:
        assert("# Skipped" in o)
    else:
        assert("# Skipped" not in o)

    if verbose:
        assert("diff_git.txt" in o)
    else:
        assert("diff_git.txt" not in o)

    if notfound:
        assert("File not found" in o)
    else:
        assert("File not found" not in o)

    assert("if        -    {0} {1}".format(4 * multiply, "####" * multiply) in o)
    assert("atoi        -    {0} {1}".format(2 * multiply, "##" * multiply) in o)
    assert("Deprecated -   {0} {1}".format(3 * multiply, "###" * multiply) in o)
