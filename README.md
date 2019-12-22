# pokalint

This is simple linting framework based on pattern matching.
It helps detect 'poka' (mistakes) in code review or self check.

## Features

* Detect and report specific patterns from source code or diff text  
  Can be used for:
  * Detect deprecated function
  * Detect typo in identifier
  * Detect forgot to erase debugging / temporary code
* Report numerical information
  * Number of diff-blocks / changed lines
  * Number of specific keywords
  * List of function definitions (Not very accurate 😛)
  * Number of function calls (Not very accurate 😝)
* Behavior can be customized by [setting file](#Setting-file)

## Usage

```
pokalint.py [-r] [-v] [--help] [FILE [FILE ...]]

-r, --recursive : Search file and directories recursively
-v, --verbose   : Output a file path being processing
```

* The pokalint.py can receives diff-text (unified format) on STDIN.
* Use "pokalint_setting.json" in the same directory as pokalint.py.

## Example use

```
# Input a diff text from STDIN
> git diff HEAD | pokalint.py

# Input a source code from argument
> pokalint.py -v hoge.cpp hoge.h
```

## Setting file

The setting file supports JSON format.

### Format

```c
{
    "target-filetype" : {
        "{filetype-name}" : [ "{pattern}", ... ]
    }
    // Option: Setting for function counter
    "language-setting" : {
        "function-declaration" : {regex-pattern},
        "function-definition" : {regex-pattern},
        "function-call" : {regex-pattern},
        // Words not use as function name
        "function-exclude" : [{word}, ...]
    }
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
            {
                // Required:
                "pattern" : "{pattern}",
                // Optional: Output {message} on warning
                "message" : "{message}",
                // Optional: Only apply this pattern for specific file types
                "only" : ["{filetype-name}", ...]
            },
            :
        ],
        :
    }
}
```
Note: "\\" In back-slash in regular expressions must be escaped. (e.g. "/\\\\w+_\\\\d+/")
