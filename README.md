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

```c
{
    "counter" : {
        "{category-name}" : [ "{pattern}", ... ]
        :
    },
    "warning" : {
        "{category-name}" : [

            // Format 1
            // In {pattern} can specify text or regular-expression.
            // - "{text-pattern}",
            // - "/{regex-pattern}/",
            // - "/{regex-pattern}/i"  // Ignore case
            "{pattern}",

            // Format 2
            // Output {message} on warning
            {
                "pattern" : "{pattern}",
                "message" : "{message}"
            },

            :
        ],
        :
    }
}
```
* "\\" In back-slash in regular expressions must be escaped. (e.g. "/\\\\w+_\\\\d+/")
