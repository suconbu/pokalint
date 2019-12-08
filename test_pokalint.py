#!/usr/bin/env python3

from pokalint import *

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
    with open("./test_gitdiff.txt") as f:
        r = i.inspect(f.readlines())
    assert(r)
    assert(r.added_block_count == 9)
    assert(r.deleted_block_count == 2)
    assert(r.replaced_block_count == 1)
    assert(r.pure_added_line_count == 46)
    assert(r.replace_added_line_count == 1)
    assert(r.pure_deleted_line_count == 3)
    assert(r.replace_deleted_line_count == 1)
    r.output(False)
    o, e = capfd.readouterr()
    verify_output(o)

def test_main(capfd):
    main(["pokalint.py", "./test_gitdiff.txt"])
    o, e = capfd.readouterr()
    verify_output(o)

def verify_output(o):
    assert("if        -    4 ####" in o)
    assert("atoi        -    2 ##" in o)
    assert("Deprecated -   3 ###" in o)
