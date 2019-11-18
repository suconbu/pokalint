#!/usr/bin/env python3

def __get_func(code):
    def func(text, bold=False):
        return "\033[{0}{1}m{2}\033[0m".format(
            "1;" if bold else "",
            code,
            text)
    return func

red = __get_func(31)
green = __get_func(32)
yellow = __get_func(33)
blue = __get_func(34)
magenta = __get_func(35)
cyan = __get_func(36)
white = __get_func(37)
default = __get_func(39)
