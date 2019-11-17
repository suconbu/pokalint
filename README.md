# pokalint

Find and report specific pattern from the diff of code to avoid careless mistakes.

# Usage

```
pokalint.py [SETTING-FILE]
```

* The pokalint.py receives diff-text on STDIN.
* If `SETTING-FILE` is omitted, use "pokalint_setting.json" in the same directory as pokalint.py.

## Example use

```
> git diff | pokalint.py

# Deprecated - NOK:2

src/hoge.cpp:35
   atoi("1");
   ^^^^

src/hoge.cpp:36
   atoll("10");
   ^^^^^

# Typo - NOK:1

src/hoge.h:33
  int chackColor(const char* color);
      ^^^^^
```

# Setting file

The setting file supports JSON format.

## Format

```json
{
    "{category-name}" : [
        "{text-pattern}",
        "/{regex-pattern}/",
        "/{regex-pattern}/i"  // Ignore case
    ],
    :
}
```
* "\\" In regular expressions must be escaped. (e.g. "/\\\\w+_\\\\d+/")
