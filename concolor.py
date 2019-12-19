#!/usr/bin/env python3

def get(text, color, bold=False):
    code = {"red":31, "green":32, "yellow":33, "blue":34, "magenta":35, "cyan":36, "white":37, "default":39}.get(color, 39)
    return "\033[{0}{1}m{2}\033[0m".format("1;" if bold else "", code, text)
