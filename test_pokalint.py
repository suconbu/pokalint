#!/usr/bin/env python3

from pokalint import *

def test_pattern():
    p = Pattern("hoge")
    assert(p.match("This is hoge."))
    p = Pattern("/\\bhoge\\b/")
    assert(p.match("This is hoge."))
    assert(not p.match("This is hogeee."))
    p = Pattern("/\\bhoge\\b/i")
    assert(p.match("This is hoge."))
    assert(p.match("This is Hoge."))
    assert(p.match("This is HOGE."))
