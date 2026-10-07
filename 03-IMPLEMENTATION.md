# Implementation walkthrough

This page reads `hash_identifier.py` from top to bottom with you. Every Python feature gets explained the first time it shows up. If you're brand new to Python, read this with the source file open in another window so you can see the lines we're talking about.

> Throughout this page, we say "the source file" to mean `hash_identifier.py`. Open it now: `code hash_identifier.py`, or `nano hash_identifier.py`, or whatever editor you use.

## 1. The file header

```python
"""
©AngelaMos | 2026
hash_identifier.py

Identify what kind of hash a string is, by inspecting its shape
...
"""
```

That triple-quoted block at the very top of the file is a **module docstring**. In Python, anything inside `"""..."""` is a string literal. When the file is loaded, Python sees this string sitting at the top with no name attached to it, and treats it as documentation for the whole module. You can read it later with `help(hash_identifier)` or by hovering over the import in an IDE.

The first line, `©AngelaMos | 2026`, is the copyright marker required by every file in this repo. The second line is the filename. Then a longer human-readable explanation of what the file does. You'll see the same pattern in every file in `PROJECTS/foundations/`.

> **Why a docstring instead of a comment?** Python has both. A `# comment` is stripped before the code runs. A `"""docstring"""` is stored on the module/function/class and is available at runtime via `__doc__`. Tools like Sphinx, mkdocs, and your IDE's hover help all read docstrings, not comments. Rule of thumb: use docstrings for "what this thing is and how to use it," and use comments for "why this *specific line* exists."

## 2. Imports

```python
import argparse
import sys
from dataclasses import dataclass
from typing import Literal

from rich.console import Console
from rich.table import Table
```

An `import` statement brings code from another file into yours. Python ships with hundreds of modules in its **standard library** (always available, no install needed) and you can install more from [PyPI](https://pypi.org/) using `uv add <package>`.

There are two `import` shapes:

- `import argparse` — imports the whole module under its own name. You then refer to things inside it as `argparse.ArgumentParser`.
- `from dataclasses import dataclass` — imports just one thing out of the module, so you can use it bare: `dataclass` instead of `dataclasses.dataclass`.

Use the second form when you only need one or two things and they have descriptive names. Use the first form when you'd otherwise pull in a bunch of names that might collide with yours.

A blank line separates standard-library imports from third-party imports. That's a [PEP 8](https://peps.python.org/pep-0008/#imports) convention. Linters will yell at you if you mix them.

Tour of what we just imported:

| Import       | What it is                                                                    | Why we need it                                            |
| ------------ | ----------------------------------------------------------------------------- | --------------------------------------------------------- |
| `argparse`   | Standard-library CLI argument parser                                          | Turns `sys.argv` into nice attributes (`args.hash`)       |
| `sys`        | Standard library, talks to the Python interpreter                             | We use `sys.exit(...)` to set the program's exit code     |
| `dataclass`  | A decorator that turns a class into a small record                            | Saves us writing `__init__` for `HashCandidate`           |
| `Literal`    | A type hint meaning "this value is one of these specific strings"             | Pins `confidence` to `"high" / "medium" / "low"`          |
| `Console`    | Third-party, from the [`rich`](https://github.com/Textualize/rich) library    | The thing that draws colored text to the terminal         |
| `Table`      | Also from `rich`                                                              | Builds the colored ASCII table we print to the user       |

## 3. The Literal type

```python
Confidence = Literal["high", "medium", "low"]
```

This line creates a **type alias**. We give the type `Literal["high", "medium", "low"]` a friendly name, `Confidence`, and use that name everywhere else.

A `Literal` type says: "the value of this thing must be exactly one of these specific values — not just any string." With mypy (our type checker) turned on, code like this:

```python
candidate = HashCandidate(algorithm="MD5", confidence="hgih", reason=...)
                                                       ^^^^^^
                                                       typo!
```

would be flagged at edit time, before you ever run the code. Without `Literal`, the type would be `str` and `"hgih"` would slide by until a user noticed the misspelled output.

We picked `Literal` over Python's `Enum` because for small fixed sets of strings, `Literal` is lighter weight — no separate class definition, no `.value` attribute to remember. (For bigger sets or when you need behavior on the values, `Enum` is the right choice.)

## 4. The HashCandidate dataclass

```python
@dataclass(frozen=True, slots=True)
class HashCandidate:
    """One possible identification of a hash string ..."""
    algorithm: str
    confidence: Confidence
    reason: str
```

This is the data record the brain returns. Let's unpack what's happening:

- **`class HashCandidate:`** defines a new type called `HashCandidate`. A class is a blueprint for objects.
- **`algorithm: str`** declares an attribute named `algorithm` of type `str` (a string). The colon-then-type syntax is a **type annotation**. It's optional in Python but heavily used in modern code.
- **`@dataclass(...)`** is a *decorator*. A decorator is a function that wraps your class and modifies it. The `@dataclass` decorator looks at the three attributes you declared (`algorithm`, `confidence`, `reason`) and generates an `__init__` method, a `__repr__` method, and a few other dunder methods automatically. Without `@dataclass`, you'd have to write:

  ```python
  class HashCandidate:
      def __init__(self, algorithm: str, confidence: Confidence, reason: str):
          self.algorithm = algorithm
          self.confidence = confidence
          self.reason = reason
      def __repr__(self):
          return f"HashCandidate(algorithm={self.algorithm!r}, ...)"
      def __eq__(self, other):
          ...
  ```

  `@dataclass` writes all that for you.

- **`frozen=True`** makes instances immutable. After the object is built, `candidate.algorithm = "different"` raises `FrozenInstanceError`. This is what makes `HashCandidate` a **value object** — like an integer or a tuple, it doesn't change after creation.

- **`slots=True`** is a memory optimization. By default, every Python object has a `__dict__` so you can add arbitrary attributes to it on the fly. We don't want that — the three fields are all we'll ever have. `slots=True` tells Python to allocate a fixed array for the three fields, skipping the dict. Faster, smaller, and `obj.typo = "anything"` now also fails (which is good — it catches bugs).

You'll use both flags together a lot for tiny data records. Together they say "this is a record, treat it like one."

## 5. The PREFIX_RULES table

```python
PREFIX_RULES: list[tuple[str, str, str]] = [
    ("$argon2id$", "Argon2id", "modern PHC string, the current standard"),
    ("$argon2i$",  "Argon2i",  "PHC string, side-channel-resistant variant"),
    ...
]
```

This is a `list` of `tuple`s. Let's break that down.

A **list** is Python's basic ordered container. You write it with square brackets: `[1, 2, 3]`. You can add to it, remove from it, index into it (`items[0]`).

A **tuple** is like a list but immutable. You write it with parentheses: `(1, 2, 3)`. You can read from it but you can't change it after creation. Tuples are the right container when the *position* of each value has meaning — like coordinates `(x, y)`, or here, "the prefix, the algorithm name, and the note" always in that order.

So `PREFIX_RULES` is a list of 3-tuples. Each tuple says "if you see this prefix, the algorithm is this name, and here is a short note about it."

The type annotation `list[tuple[str, str, str]]` says exactly that: "a list whose elements are tuples of three strings." This is purely for the human reader and for mypy — at runtime Python doesn't enforce it.

> **Why a list and not a dict?** A dict would let us look up by prefix in O(1) time. But our prefixes are not all the same length — `$2b$` is 4 chars, `$argon2id$` is 10. There's no fast "is this string a prefix of that string for any key in my dict" operation, so we walk the list. Performance is fine because the list is short (~25 entries) and we only do this once per program invocation.

Notice the comment groupings — `# Argon2 family`, `# bcrypt and its many variants` — these are the only kind of comment we use heavily in foundations-tier projects. They name *sections* of related data so the reader can scan.

The order of entries matters when two prefixes could overlap. Specifically, `$argon2id$` must come before `$argon2$` because `"$argon2id$something".startswith("$argon2$")` would *also* be true if `$argon2$` were in our table. We list more specific prefixes first so they match first.

## 6. The HEX_LENGTH_RULES table

```python
HEX_CHARSET: frozenset[str] = frozenset("0123456789abcdefABCDEF")
_HEX_UPPER_CHARSET: frozenset[str] = frozenset("0123456789ABCDEF")

HEX_LENGTH_RULES: dict[int, list[str]] = {
    16:  ["MySQL323", "CRC-64"],
    32:  ["MD5", "NTLM", "MD4", "RIPEMD-128"],
    40:  ["SHA-1", "RIPEMD-160"],
    ...
}
```

A **set** is an unordered container of unique values. A **frozenset** is a set you can't modify after creation. We use frozenset here because:

1. We never need to add/remove characters from the hex alphabet — it's known and fixed.
2. Lookup (`c in HEX_CHARSET`) is O(1) — constant time. Faster than `c in "0123456789abcdef..."` which would scan the string character by character.
3. Marking it `frozenset` signals to the reader: "this is a fixed constant, don't try to mutate it."

A **dict** (dictionary) is a mapping from keys to values. You write it with curly braces: `{key: value, key: value}`. Lookup is O(1) on the key.

`HEX_LENGTH_RULES` maps "length-in-hex-chars" to "list of algorithm names that produce that length." So `HEX_LENGTH_RULES[32]` is `["MD5", "NTLM", "MD4", "RIPEMD-128"]` — the four algorithms that produce a 32-hex-character output.

`_HEX_UPPER_CHARSET` starts with an underscore. Convention: **leading underscore means module-private.** It's saying "this is an implementation detail, not part of the public interface." Python doesn't enforce this, but every linter does. The uppercase variant exists because MySQL5 prints its hex in uppercase only (`%02X` C format), so we use a tighter charset to avoid false positives on hand-typed inputs.

## 7. The `_is_hex` helper

```python
def _is_hex(text: str) -> bool:
    """Return True iff every character in text is a hex digit and text is non-empty"""
    return bool(text) and all(c in HEX_CHARSET for c in text)
```

A `def` statement defines a function. Reading this signature:

- `def _is_hex(text: str) -> bool:` declares a function named `_is_hex` that takes one argument `text` of type `str` and returns a `bool` (True or False).
- The leading underscore makes it module-private.

The body is one line. Let's read it right to left:

- `(c in HEX_CHARSET for c in text)` is a **generator expression**. It produces a sequence of booleans: for each character `c` in `text`, yield `True` if `c` is in our hex charset, else `False`.
- `all(...)` takes that sequence and returns `True` only if *every* yielded value is True. Equivalent to "every character of text is a hex digit."
- `bool(text)` evaluates to `False` if `text` is empty, `True` otherwise. We need this guard because `all([])` of an empty sequence returns True (mathematically reasonable, practically annoying — an empty string is not a valid hex string).
- `... and ...` short-circuits: if `bool(text)` is False, we don't bother checking `all(...)`.

The word `iff` in the docstring is shorthand for "if and only if." Math nerds and CS people use it constantly; it means a biconditional.

## 8. MySQL5 detection

```python
_MYSQL5_HEX_BODY_LENGTH = 40
_MYSQL5_TOTAL_LENGTH = _MYSQL5_HEX_BODY_LENGTH + 1


def _is_mysql5(text: str) -> bool:
    """Return True for MySQL5 password format: `*` then 40 UPPERCASE hex chars ..."""
    if len(text) != _MYSQL5_TOTAL_LENGTH or not text.startswith("*"):
        return False
    body = text[1:]
    return all(c in _HEX_UPPER_CHARSET for c in body)
```

The two constants at the top come from one of the rules of this codebase: **no magic numbers**. Compare:

```python
if len(text) != 41 or not text.startswith("*"):
    return False
```

vs:

```python
if len(text) != _MYSQL5_TOTAL_LENGTH or not text.startswith("*"):
    return False
```

Both work. Only the second one tells the reader *why* 41 is the right number (it's 40 hex chars for the body plus 1 for the leading `*`).

The function does three things:

1. Check the total length is exactly 41 and the first character is `*`. If not, bail with False.
2. Slice off the leading `*` using `text[1:]`. Python slicing: `text[start:stop]` gives you the substring from index `start` (inclusive) to `stop` (exclusive). Omitting `stop` means "to the end." So `text[1:]` means "everything from index 1 onwards" — i.e. drop the first character.
3. Check that every character in the body is in our uppercase-only hex charset.

The docstring contains an important caveat: we *cannot* use `body.isupper()` to enforce uppercase, because Python's `str.isupper()` returns False for a string with no cased characters at all. So `"0123456789ABCDEF...".isupper()` would correctly return True, but an all-digit body would return False — wrongly rejecting valid input. Checking membership in `_HEX_UPPER_CHARSET` is the test that actually matches the spec.

This is the kind of subtle gotcha you only learn from being burned. Worth memorizing: **don't use `.isupper()` / `.islower()` as a "this string contains only uppercase chars" check.**

## 9. DES crypt detection

```python
_DESCRYPT_CHARSET: frozenset[str] = frozenset(
    "./0123456789"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
)
_DESCRYPT_TOTAL_LENGTH = 13


def _is_descrypt(text: str) -> bool:
    """Return True for traditional 13-char DES crypt (legacy /etc/passwd) ..."""
    return (
        len(text) == _DESCRYPT_TOTAL_LENGTH
        and all(c in _DESCRYPT_CHARSET for c in text)
    )
```

DES crypt is the *original* Unix password hash format from the 1970s. No prefix, no salt marker, just 13 characters from a specific 64-character alphabet.

The charset definition uses **string literal concatenation**: three string literals sitting next to each other are automatically joined by Python at parse time. So this:

```python
"./0123456789"
"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
"abcdefghijklmnopqrstuvwxyz"
```

is exactly the same as:

```python
"./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
```

But the split form is much easier to read. This works for any sequence of adjacent string literals — useful when wrapping long strings.

`_is_descrypt` itself is two checks: right length, right alphabet. Both must be true (`and`). The whole expression is wrapped in parentheses just for visual layout — Python allows you to split expressions across lines if they're inside `()`, `[]`, or `{}`.

## 10. The `identify` function — the brain

This is the main attraction. It's about 100 lines long and follows the six-step pipeline from [02-ARCHITECTURE.md](./02-ARCHITECTURE.md).

### 10a. The pylint silencing comment

```python
# pylint: disable=too-many-return-statements,too-many-branches
```

This comment turns off two specific pylint warnings *for this function only*. Pylint normally complains about functions with lots of `return` statements or lots of branches, because they're usually a sign that you should refactor.

We're keeping the warnings off because in this case the branching *is* the structure. Six numbered steps, each potentially returning a result — refactoring them into six helper functions would scatter the pipeline across the file and make it harder, not easier, to read. So we acknowledge the warnings, explain why we're keeping them off in the inline comment block above, and turn them off explicitly.

> **Rule of thumb on silencing linters:** never silence broadly. Always silence the *specific* warning, on the *specific* function, with a comment that explains why. If you find yourself silencing the same warning everywhere, your linter config is wrong, not your code.

### 10b. The signature and docstring

```python
def identify(raw_input: str) -> list[HashCandidate]:
    """Return ranked candidates for what algorithm produced `raw_input` ..."""
```

Takes a string. Returns a list of `HashCandidate` objects. That's the whole contract. The function does not raise exceptions for unknown inputs — it returns an empty list instead. (Throwing exceptions for "I don't know" forces every caller to wrap the call in try/except. Returning an empty list is cleaner.)

The docstring is **Numpy-style**: it has labeled sections (`Parameters`, `Returns`) with the parameter name on its own line and the description indented underneath. Numpy style is what most scientific Python uses. The other big style is Google ("Args:" and "Returns:" with colons), and you'll see both in the wild. Either is fine; just pick one and be consistent.

### 10c. Trim and bail on empty

```python
text = raw_input.strip()

if not text:
    return []
```

`str.strip()` returns a *new* string with leading and trailing whitespace removed. (Strings are immutable in Python — every "modifying" method actually returns a new string.) We do this because hashes copy-pasted from terminals often arrive with trailing newlines or leading spaces.

We do *not* lowercase the text. Some formats (MySQL5) are case-sensitive on purpose.

The `if not text:` check catches the empty string. In Python, an empty string is **falsy** — it counts as False in a boolean context. So `not text` is True when `text` is empty. Same for empty list, empty dict, `None`, and `0`. Get used to this — it's one of Python's defining features.

### 10d. Step 1 — walk PREFIX_RULES

```python
for prefix, algorithm, note in PREFIX_RULES:
    if text.startswith(prefix):
        return [
            HashCandidate(
                algorithm=algorithm,
                confidence="high",
                reason=f"prefix `{prefix}` — {note}",
            )
        ]
```

A `for ... in ...` loop iterates over each element of a sequence. Here, each element of `PREFIX_RULES` is a 3-tuple, so we **unpack** it directly into three variables — `prefix`, `algorithm`, `note` — in one go. This is called *tuple unpacking* and it's used constantly in Python.

`text.startswith(prefix)` is a method on `str` that returns True if `text` begins with `prefix`. There's also `endswith`, by the way.

`f"..."` is an **f-string** (formatted string literal). Anything inside `{}` is evaluated and inserted into the string. So `f"prefix `{prefix}` — {note}"` produces something like `"prefix \`$2b$\` — bcrypt PHC string, 2b variant (current)"`. F-strings are the modern way to format strings in Python (3.6+); avoid the older `%` and `.format()` styles in new code.

The function returns a list containing one `HashCandidate`. We use keyword arguments (`algorithm=algorithm`) instead of positional ones so the call reads clearly even if you don't remember the parameter order.

The whole `if text.startswith(prefix):` check returns immediately on the first match. This is fine because the table is designed so that no two prefixes can match the same input (the longer, more specific ones come first).

### 10e. Step 2 — special non-PHC shapes

NetNTLMv2, NetNTLMv1, MySQL5, DES crypt. Each gets its own block.

```python
if "::" in text and text.count(":") >= 4:
    parts = text.split(":")
    if (len(parts) >= 6 and len(parts[4]) == 32 and _is_hex(parts[4])):
        return [HashCandidate(algorithm="NetNTLMv2", ...)]
    if (len(parts) >= 6 and len(parts[3]) == 48 and _is_hex(parts[3])):
        return [HashCandidate(algorithm="NetNTLMv1", ...)]
```

A few Python features here:

- `"::" in text` returns True if the substring `"::"` appears anywhere in `text`. The `in` operator works on strings (substring check), lists (membership), dicts (key lookup), sets (membership), and any iterable.
- `text.count(":")` returns how many times `:` appears in the string.
- `text.split(":")` returns a list of substrings, splitting on `:`. So `"a:b:c".split(":")` gives `["a", "b", "c"]`.
- `parts[3]` indexes into the list. Python uses zero-based indexing, so `parts[3]` is the *fourth* element.

NetNTLMv2 records look like `user::domain:challenge:hmac(32 hex):blob`. We split on `:`, then look at part index 4 (the hmac field): if it's exactly 32 hex characters, we've got a v2. NetNTLMv1 looks similar but the field at index 3 is 48 hex chars (the LM hash). We test v2 *first* because v2's distinguishing field at index 4 is more specific.

This is the messiest step in the whole function. NetNTLM records were not designed to be pretty — they evolved from Microsoft authentication protocols of the 1990s. The shape match is the best we can do without parsing the entire NTLM protocol.

```python
if _is_mysql5(text):
    return [HashCandidate(algorithm="MySQL5", confidence="high", ...)]

if _is_descrypt(text):
    return [HashCandidate(algorithm="DES crypt", confidence="medium", ...)]
```

Calls our helpers. Note that MySQL5 gets **HIGH** confidence (the `*` + 40 uppercase hex shape is essentially unique) while DES crypt gets **MEDIUM** (a 13-char `./0-9A-Za-z` string could plausibly be other things — some session IDs, some encoded values). Honesty is a feature.

### 10f. Step 3 — hex + length lookup

```python
if _is_hex(text):
    algorithms = HEX_LENGTH_RULES.get(len(text), [])
    candidates: list[HashCandidate] = []
    for index, algorithm in enumerate(algorithms):
        confidence: Confidence = "medium" if index == 0 else "low"
        label = (
            "most likely candidate at this length"
            if index == 0 else "also possible at this length"
        )
        candidates.append(
            HashCandidate(algorithm=algorithm, confidence=confidence, reason=...)
        )
    return candidates
```

Three new Python features here:

- **`dict.get(key, default)`** returns the value if the key exists, or `default` if not. So `HEX_LENGTH_RULES.get(len(text), [])` returns the list of algorithms at this length, or an empty list if no rule exists for this length. This avoids a `KeyError` exception that would happen with `HEX_LENGTH_RULES[len(text)]` on an unknown length.
- **`enumerate(iterable)`** is a built-in that wraps an iterable and yields `(index, value)` pairs. So `for index, algorithm in enumerate(algorithms)` walks the list and gives us both the position and the value. The first algorithm gets index 0, the second gets index 1, etc.
- **Ternary expression**: `value_if_true if condition else value_if_false`. So `"medium" if index == 0 else "low"` evaluates to `"medium"` for the first item and `"low"` for the rest. This is the Python equivalent of `cond ? a : b` in C/JavaScript.

The first algorithm at each length is the one that's most common in 2026 — MD5 at length 32, SHA-1 at length 40, SHA-256 at length 64. The list ordering in `HEX_LENGTH_RULES` is by descending prevalence, so "first" really does mean "most likely."

`candidates.append(item)` adds an item to the end of the list. `list[T]` is a generic type — `list[HashCandidate]` means "a list whose elements are HashCandidate objects." The empty list literal `[]` is unannotated, so we write `candidates: list[HashCandidate] = []` to tell mypy what we intend the list to hold.

### 10g. Step 4 — generic PHC fallback

```python
if text.startswith("$"):
    rest = text[1:]
    if "$" in rest:
        algo_name = rest.split("$", 1)[0]
        if algo_name and all(c.isalnum() or c in "-_" for c in algo_name):
            return [HashCandidate(algorithm=f"PHC string ({algo_name})", ...)]
```

If the input starts with `$` but didn't match any of our specific rules, it might still be a PHC string from an algorithm we don't have a rule for. We try to extract the algorithm name and report it as a generic PHC at LOW confidence.

- `text[1:]` slices off the leading `$`.
- `rest.split("$", 1)` splits on `$` but only once — the optional second argument to `split` is the max number of splits. So `"argon2id$v=19$...".split("$", 1)` returns `["argon2id", "v=19$..."]`. Without the `1`, it would split on every `$` and we'd lose information.
- `[0]` takes the first element of the resulting list.
- `c.isalnum()` is a `str` method returning True if `c` is a letter or digit. We use this to validate that the algorithm name field contains only PHC-legal characters (alphanumeric plus `-` and `_`). Anything weirder and we bail rather than make up an algorithm name from garbage.

The whole step is gated on the algorithm name being non-empty AND every character being legal. Better to report nothing than to guess wildly.

### 10h. Step 5 — shape hints

```python
if text.startswith("eyJ"):
    return [HashCandidate(algorithm="JWT (not a hash)", ...)]

if any(c in text for c in "+/=") and len(text) > 8:
    return [HashCandidate(algorithm="Base64 blob (not a hash)", ...)]
```

People paste JWTs and base64 blobs into hash identifiers all the time. Rather than returning a silent "no match," we point out what they probably pasted.

JWTs always start with `eyJ` because the JWT header is JSON like `{"alg":"HS256","typ":"JWT"}`, and the bytes `{"` base64-encoded begin with `eyI` or `eyJ`. The leading `eyJ` is essentially diagnostic for JWTs.

`any(c in text for c in "+/=")` is a generator expression inside `any()` — mirror of the `all(...)` we used in `_is_hex`. `any()` returns True if *any* element of the sequence is True. Together: "is there any character in `'+/='` that appears in `text`?" If yes, the input contains base64-only characters and cannot be a hex hash.

The `len(text) > 8` floor exists because a short string like `"a+b=c"` might trip the base64 check accidentally. We require enough length to be sure it's actually base64, not a math expression.

### 10i. Step 6 — give up

```python
return []
```

Empty list. The CLI prints "could not identify" when it sees this. Always better to admit defeat than to lie with confidence.

## 11. The CLI layer

### 11a. The argument parser

```python
def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hashid", description="...")
    parser.add_argument("hash", help="The hash string to identify ...")
    parser.add_argument("--top", "-n", type=int, default=5, help="...")
    return parser
```

`argparse.ArgumentParser` is the standard library's CLI parser. We set:

- `prog="hashid"` — the program name shown in help text.
- `description="..."` — the one-line summary at the top of `--help`.

Then we add two arguments:

- **`"hash"`** — a positional argument. The user types `hashid <hash>`. Required. After parsing, `args.hash` holds the string.
- **`"--top", "-n"`** — an optional flag with both a long form (`--top 3`) and short form (`-n 3`). `type=int` converts the string the user typed into an integer. `default=5` is what you get if the user doesn't pass it.

The function *returns* the parser without calling `.parse_args()`. Why? So the test file can build the parser, inspect it, run it on test input, etc., without actually executing the CLI. **Separating construction from execution is a recurring pattern for testability.** Whenever you find yourself writing `something().run()` in one line, ask whether someone needs to build that something without running it.

### 11b. The table renderer

```python
def _render_table(raw_input, candidates, console) -> None:
    table = Table(title=f"Candidates for: {raw_input.strip()}", ...)
    table.add_column("algorithm", style="bold white", no_wrap=True)
    table.add_column("confidence", no_wrap=True)
    table.add_column("reason", style="dim")

    confidence_colors: dict[Confidence, str] = {
        "high": "green",
        "medium": "yellow",
        "low": "cyan",
    }
    for candidate in candidates:
        color = confidence_colors[candidate.confidence]
        table.add_row(
            candidate.algorithm,
            f"[{color}]{candidate.confidence}[/{color}]",
            candidate.reason,
        )
    console.print(table)
```

`rich.Table` is a class from the `rich` library. You create a Table, add columns, add rows, then print it. The library handles all the box-drawing characters, color codes, terminal-width detection, and Unicode handling.

The `f"[{color}]{candidate.confidence}[/{color}]"` syntax is `rich`'s inline color markup. `[green]text[/green]` colors `text` green. We use a dict to look up the color for each confidence level — three colors, predictable, easy to change in one place if we wanted to.

The `-> None` return type means the function doesn't return anything meaningful (it just has side effects: printing to the terminal). This is the right annotation for "this function does its work via side effects."

`console` is passed in as a parameter rather than created inside. Same idea as the parser: the test can pass a captured-output Console, the real CLI passes a real Console. Dependency injection at work.

### 11c. `main()` and the script guard

```python
def main() -> int:
    parser = _build_argument_parser()
    args = parser.parse_args()
    console = Console()

    candidates = identify(args.hash)

    if not candidates:
        console.print("[red]No identification possible.[/red] ...")
        return 1

    trimmed = candidates[:args.top]
    _render_table(args.hash, trimmed, console)

    if trimmed[0].confidence == "high":
        console.print("\n[dim]Next step: try the matching cracker ...[/dim]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`main()` is the entry point. The body reads like English:

1. Build the parser.
2. Parse `sys.argv` (`parser.parse_args()` defaults to using `sys.argv`).
3. Build a Console.
4. Run the brain on the user's input.
5. If no candidates, print an error and return exit code 1.
6. Trim to the top-N results (`candidates[:args.top]` is slicing — same as before).
7. Render the table.
8. If the top candidate is HIGH confidence, print a hint about what to do next.
9. Return exit code 0.

The function returns the exit code as an integer. We hand it to `sys.exit()` at the bottom.

The final block:

```python
if __name__ == "__main__":
    sys.exit(main())
```

is the classic Python script idiom. `__name__` is a special variable Python sets automatically:

- When you run `python hash_identifier.py`, Python sets `__name__ = "__main__"`.
- When you `import hash_identifier` from somewhere else, Python sets `__name__ = "hash_identifier"`.

So `if __name__ == "__main__":` means "only do this when the file is run directly, not when it's imported." This lets the test file `import hash_identifier` and call `identify()` without accidentally firing the CLI.

`sys.exit(N)` terminates the program with exit code N. Exit code 0 conventionally means success; non-zero means failure. Shell scripts (`if hashid "$x"; then ...`) read the exit code to decide what to do next.

## 12. Running through a real example

Let's trace what happens for `just run -- '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQNQy.uK4Of2T7G'`.

```
1. Shell invokes:    python hash_identifier.py '$2b$12$EixZ...'
2. Python runs the file. sys.argv = [".../hash_identifier.py", "$2b$12$EixZ..."]
3. Since __name__ == "__main__", call sys.exit(main()).
4. main() builds parser, calls parser.parse_args().
5. argparse sees positional arg → args.hash = "$2b$12$EixZ..."
   args.top = 5 (default).
6. main() calls identify(args.hash).

7. identify():
   text = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQNQy.uK4Of2T7G"
   text is non-empty.
   Step 1: walk PREFIX_RULES.
     First row $argon2id$ — does text start with "$argon2id$"?  no.
     ... a few more rows ...
     Row ("$2b$", "bcrypt", ...) — does text start with "$2b$"?  YES!
     return [HashCandidate(algorithm="bcrypt", confidence="high", reason="prefix `$2b$` — bcrypt PHC string, 2b variant (current)")]

8. Back in main(): candidates is non-empty.
9. trimmed = candidates[:5] → just the one candidate.
10. _render_table(args.hash, trimmed, console)
    Build a Table with title "Candidates for: $2b$12$EixZ...".
    Add three columns.
    Build one row: ("bcrypt", "[green]high[/green]", "prefix `$2b$` — ...").
    console.print(table) — rich draws the colored ASCII table to your terminal.
11. Top candidate is HIGH confidence → print the "Next step" nudge.
12. return 0.
13. sys.exit(0) — clean exit.
```

Total elapsed time: well under a millisecond for the brain, a few more for `rich` to render. Almost all of the program's runtime is `rich` drawing the table.

## 13. The test file, in brief

Open `test_hash_identifier.py` if you haven't yet. It's structured as ~25 small `test_*` functions. Each one:

1. Builds a known input.
2. Calls `identify(input)` or `_is_mysql5(input)` etc.
3. Asserts something about the output (`assert candidates[0].algorithm == "bcrypt"`).

A few interesting ones to read:

- **`test_every_prefix_rule_is_recognized_with_high_confidence`** (~line 531) — loops over `PREFIX_RULES` and confirms every row produces a HIGH-confidence match. Adds rows automatically if you add new prefixes.
- **`test_mysql5_rejects_lowercase_body`** (~line 188) — confirms the "don't lie with confidence" rule from the implementation.
- **`test_hash_candidate_is_frozen`** (~line 481) — uses `pytest.raises` to confirm that mutating a frozen dataclass raises `FrozenInstanceError`.

Run them: `just test`. The whole suite is ~30 tests and finishes in under a second.

## 14. What to try next

You've read the file. To make the knowledge stick:

1. Try `just run -- <hash>` with weird inputs — empty string (after quoting), pure digits, super long strings, hashes with trailing whitespace, JWTs, base64.
2. Open `hash_identifier.py` and add a `print()` statement inside `identify()` to see which step matches for each input. Then remove it before committing.
3. Add a new prefix to `PREFIX_RULES` — for instance, scrypt sometimes shows up with `$scrypt$` prefix. Add it, add a test, run `just test`.
4. Read **[04-CHALLENGES.md](./04-CHALLENGES.md)** for harder extension ideas.
