# Architecture

This page is about *how the code is shaped*. Not what each line does — that's the next page. Here we zoom out and look at how the pieces fit together, what data flows where, and why we picked this shape over the alternatives.

## 1. The big picture

The whole tool is one Python file: `hash_identifier.py`. Everything that runs lives in that file. There are three layers inside it:

```
┌─────────────────────────────────────────────────────────────┐
│  CLI layer  (main, _build_argument_parser, _render_table)   │
│  - reads command-line arguments                             │
│  - prints the colored table to your terminal                │
│  - returns an exit code                                     │
└──────────────────────────┬──────────────────────────────────┘
                           │ calls
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Pure-function layer  (identify)                            │
│  - the actual decision-making                               │
│  - takes a string, returns a list of HashCandidate          │
│  - touches NO files, NO network, NO global state            │
└──────────────────────────┬──────────────────────────────────┘
                           │ uses
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Data layer  (PREFIX_RULES, HEX_LENGTH_RULES, charsets)     │
│  - lookup tables describing what we know about hashes       │
│  - read-only, defined at module load time                   │
└─────────────────────────────────────────────────────────────┘
```

Reading top to bottom, the CLI layer is the **outside** of the program: it deals with the human. The pure-function layer is the **brain**: it takes a clean string in and returns a clean answer out. The data layer is the **knowledge**: every "we know X about hash Y" lives in one of those tables, not scattered through the code.

This three-way split is deliberate. We can test the brain in isolation without ever spawning a CLI — and the test file does exactly that, calling `identify()` directly. We can change how the table looks (color, layout, JSON output) without touching the brain. And we can add new hash formats by adding a row to a table, not by adding a new function.

## 2. Data flow on a single run

Here's what happens when you type `just run -- 5f4dcc3b5aa765d61d8327deb882cf99`:

```
                                            (your terminal)
                                                  │
                                                  │  "5f4dcc3b5aa765d61d8327deb882cf99"
                                                  ▼
                              ┌─────────────────────────────────────┐
                              │  argparse                           │
                              │  parses sys.argv into args.hash     │
                              └────────────────┬────────────────────┘
                                               │ args.hash = "5f4dcc..."
                                               ▼
                              ┌─────────────────────────────────────┐
                              │  identify(args.hash)                │
                              │                                     │
                              │  text = args.hash.strip()           │
                              │                                     │
                              │  ┌─────────────────────────────┐    │
                              │  │ Step 1: prefix match?       │    │
                              │  └────────────┬────────────────┘    │
                              │  no match     │                     │
                              │               ▼                     │
                              │  ┌─────────────────────────────┐    │
                              │  │ Step 2: special shape?      │    │
                              │  │  (NetNTLM / MySQL5 / DES)   │    │
                              │  └────────────┬────────────────┘    │
                              │  no match     │                     │
                              │               ▼                     │
                              │  ┌─────────────────────────────┐    │
                              │  │ Step 3: hex + length match? │    │
                              │  │  → 32 hex chars → MD5/NTLM..│ ✔  │
                              │  └────────────┬────────────────┘    │
                              │               │                     │
                              │       returns [HashCandidate, ...]  │
                              └────────────────┬────────────────────┘
                                               │
                                               ▼
                              ┌─────────────────────────────────────┐
                              │  _render_table()                    │
                              │  builds a rich.Table, prints it     │
                              └────────────────┬────────────────────┘
                                               │
                                               ▼
                                       (your terminal)

      ┌─────────────────────────────────────────────────────────┐
      │  Candidates for: 5f4dcc3b5aa765d61d8327deb882cf99       │
      │  ╭───────────┬────────────┬───────────────────────────╮ │
      │  │ algorithm │ confidence │ reason                    │ │
      │  ├───────────┼────────────┼───────────────────────────┤ │
      │  │ MD5       │ medium     │ 32 hex chars — most likely│ │
      │  │ NTLM      │ low        │ 32 hex chars — also poss. │ │
      │  │ MD4       │ low        │ 32 hex chars — also poss. │ │
      │  │ RIPEMD-128│ low        │ 32 hex chars — also poss. │ │
      │  ╰───────────┴────────────┴───────────────────────────╯ │
      └─────────────────────────────────────────────────────────┘
```

The brain is the middle box. Everything above and below it is just plumbing: getting the string in, getting the table out.

## 3. The six-step decision pipeline

The brain (`identify()`) is structured as **six numbered steps**. Each step is a chance to short-circuit and return a verdict. If a step matches, the function returns immediately. If not, control falls through to the next step.

This shape — "try the strongest signal first, fall back to weaker ones" — is called a **decision cascade** or **rule pipeline**. You'll see this pattern all over security tooling: spam filters, IDS rules, antivirus heuristics, fingerprinting. They all share the same skeleton.

```
        ┌────────────────────────────────┐
        │ Step 1: PREFIX_RULES?          │ HIGH confidence
        │ Walk the prefix table.         │ ────────►  return
        │ Any prefix start match wins.   │ first match
        └─────────────┬──────────────────┘
                      │ no match
                      ▼
        ┌────────────────────────────────┐
        │ Step 2: special shapes?        │ HIGH/MEDIUM
        │ NetNTLMv2 / NetNTLMv1 (`::`)   │ ────────►  return
        │ MySQL5  (`*` + 40 upper hex)   │ first match
        │ DES crypt  (13 chars)          │
        └─────────────┬──────────────────┘
                      │ no match
                      ▼
        ┌────────────────────────────────┐
        │ Step 3: pure hex?              │ MEDIUM/LOW
        │ If yes, look up length in      │ ────────►  return
        │ HEX_LENGTH_RULES, return all   │ ranked list
        │ candidates ranked by likelihood│
        └─────────────┬──────────────────┘
                      │ not hex
                      ▼
        ┌────────────────────────────────┐
        │ Step 4: generic `$algo$...`?   │ LOW
        │ Looks like a PHC string but    │ ────────►  return
        │ we have no specific rule.      │ generic match
        │ Report it as a generic PHC.    │
        └─────────────┬──────────────────┘
                      │ no
                      ▼
        ┌────────────────────────────────┐
        │ Step 5: shape hint?            │ LOW
        │ Looks like a JWT (eyJ...) or   │ ────────►  return
        │ base64 (`+`, `/`, `=`)?        │ "not a hash"
        │ Tell the user it's not a hash. │
        └─────────────┬──────────────────┘
                      │ no
                      ▼
        ┌────────────────────────────────┐
        │ Step 6: give up.               │ none
        │ Return empty list.             │ ────────►  []
        │ CLI prints "could not identify"│
        └────────────────────────────────┘
```

Order matters here, and the order isn't arbitrary. We always try **the most specific test first** and **the most general test last**:

1. PHC prefixes are dead giveaways — the hash itself names the algorithm.
2. Special shapes (NetNTLM, MySQL5, DES crypt) are also strong: they have distinctive structures.
3. Hex + length is a *narrowing* signal, not a definitive one — it picks a family, not a member.
4. Generic PHC fallback catches hashes that *look* PHC-shaped but aren't in our table.
5. Shape hints handle the common "I pasted the wrong thing" case (people drop JWTs into hash identifiers all the time).
6. Empty list = honest "I don't know."

If we reversed the order — say, checked length before prefix — we would misclassify a bcrypt hash as "60 hex chars, no length rule" because we'd never look at its `$2b$` prefix. Order encodes priority.

## 4. The HashCandidate object

The brain doesn't return a string — it returns a list of `HashCandidate` objects. A candidate has three fields:

```
┌─────────────────────────────────────────────────────────────┐
│  HashCandidate                                              │
│                                                             │
│    algorithm:   str         e.g. "MD5", "bcrypt", "SHA-256" │
│    confidence:  Literal     "high" | "medium" | "low"       │
│    reason:      str         "prefix `$2b$` — bcrypt PHC..." │
│                                                             │
│  frozen=True   ── immutable, can't be mutated after creation│
│  slots=True    ── memory-efficient (no __dict__)            │
└─────────────────────────────────────────────────────────────┘
```

The shape is intentional. **`algorithm`** is what hashcat wants to know. **`confidence`** tells the human reader how much to trust this guess. **`reason`** is the *evidence* — a one-line explanation of why the tool made this guess. The reason field is what makes the tool teachable: the user sees not just "bcrypt" but "prefix `$2b$` — bcrypt PHC string, 2b variant (current)."

We use `@dataclass(frozen=True, slots=True)` instead of writing a class with `__init__` and `__repr__` by hand:

- **`frozen=True`** means once you build a `HashCandidate`, you can't mutate it. If somewhere in the code tried `candidate.algorithm = "something else"`, Python would raise `FrozenInstanceError`. This makes the data flow predictable: a candidate that comes out of `identify()` is the same candidate everywhere it shows up later.
- **`slots=True`** is a memory optimization. Without slots, every instance carries around a `__dict__` for adding attributes on the fly. We don't need that, so we turn it off and save memory.

Both flags also signal *intent* to a reader: "this is a value object, not a mutable bag of state." That signal matters more than the bytes saved.

## 5. The data tables as the source of truth

If you wanted to add a new hash format to this tool, you would not write new logic. You would add a row to one of these tables:

```
PREFIX_RULES: list of (prefix, algorithm, note)
─────────────────────────────────────────────────
("$argon2id$", "Argon2id", "modern PHC string..."),
("$2b$",       "bcrypt",   "bcrypt PHC string..."),
("$6$",        "SHA-512 crypt", "Unix crypt..."),
... ~25 more rows


HEX_LENGTH_RULES: dict of {length_in_hex_chars: [algorithms]}
─────────────────────────────────────────────────────────────
32:  ["MD5", "NTLM", "MD4", "RIPEMD-128"],
40:  ["SHA-1", "RIPEMD-160"],
64:  ["SHA-256", "SHA3-256", "BLAKE2s-256", "RIPEMD-256"],
128: ["SHA-512", "SHA3-512", "BLAKE2b-512", "Whirlpool"],
... etc


HEX_CHARSET, _HEX_UPPER_CHARSET, _DESCRYPT_CHARSET
──────────────────────────────────────────────────
The alphabets used by each format. frozenset for fast lookup.
```

This is called a **data-driven design**. The rules live in data, not code. Three benefits:

1. **Adding a new format is one line.** No new function, no new test scaffolding to write.
2. **The rules are inspectable.** You can read `PREFIX_RULES` and immediately see every format the tool knows.
3. **The rules are testable.** The test file iterates over `PREFIX_RULES` and confirms each prefix is recognized — so the data and the behavior cannot drift out of sync.

When you read the implementation page next, watch how few of the function bodies have *if/elif/elif* chains. The decisions happen inside table lookups, not inside conditionals. That's the data-driven design at work.

## 6. Two helper functions

The brain is one big function (`identify`), but two small helpers live next to it. They both answer yes/no questions about the input string:

```
┌──────────────────────────────────────────────────────────┐
│  _is_hex(text) -> bool                                   │
│    "Is every character of text a valid hex digit?"       │
│    Used in step 3 to decide whether to look up length.   │
├──────────────────────────────────────────────────────────┤
│  _is_mysql5(text) -> bool                                │
│    "Does text look like `*` + 40 uppercase hex chars?"   │
│    Used in step 2 for MySQL5 detection.                  │
├──────────────────────────────────────────────────────────┤
│  _is_descrypt(text) -> bool                              │
│    "Is text 13 chars from `./0-9A-Za-z`?"                │
│    Used in step 2 for legacy DES crypt detection.        │
└──────────────────────────────────────────────────────────┘
```

The leading underscore (`_is_hex`, not `is_hex`) is a Python convention meaning **"this is module-private."** It says to other developers: "this is an implementation detail of `hash_identifier.py`; don't import it from somewhere else." Python doesn't *enforce* this — you can still import private names — but every linter and every reviewer will flag you if you do.

The helpers are tiny on purpose. Each one is a single boolean question. We pull them out of `identify()` not because they're complicated but because giving them a name makes `identify()` read like English: "if `_is_hex(text)`, do hex-length matching." If we inlined the test, the eye would have to parse it.

## 7. The CLI layer

The CLI layer is the part the human actually interacts with. It does three things:

```
┌────────────────────────────────────────────────────────────┐
│ _build_argument_parser()                                   │
│   Sets up argparse — defines that the program takes one    │
│   positional argument (`hash`) and an optional `--top N`   │
│   flag. Returns a configured parser.                       │
│                                                            │
│   Pulled out of main() so tests can build the parser       │
│   without actually running the CLI.                        │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ _render_table(raw_input, candidates, console)              │
│   Builds a rich.Table object, adds one row per candidate,  │
│   colors the confidence column (green/yellow/cyan),        │
│   and prints it.                                           │
│                                                            │
│   Takes the rich Console as an argument so tests can pass  │
│   a captured-output Console and verify what got printed.   │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ main()                                                     │
│   Parses args, calls identify(), prints the table.         │
│   Returns an exit code:                                    │
│     0 → at least one candidate found                       │
│     1 → no candidates (printed an error message)           │
│                                                            │
│   The exit code lets shell scripts do                      │
│       `if hashid "$x"; then ...`                           │
│   to react to whether identification succeeded.            │
└────────────────────────────────────────────────────────────┘
```

The crucial design choice in the CLI layer is **dependency injection**. `_render_table` takes a `Console` object as a parameter instead of creating one inside. That sounds fancy, but it just means: "give me the printer to use." The function doesn't care if you give it a real terminal Console or a test Console that captures output to a string. This makes the function testable without writing to your real terminal during tests.

## 8. The test file mirrors the brain

`test_hash_identifier.py` is structured to mirror `hash_identifier.py`. It tests every behavior the tool claims to have:

```
test_bcrypt_prefix_is_recognized            ── covers PREFIX_RULES row $2b$
test_argon2id_prefix_is_recognized          ── covers PREFIX_RULES row $argon2id$
test_apr1_prefix_is_recognized              ── covers PREFIX_RULES row $apr1$
test_sha512_crypt_prefix_is_recognized      ── covers PREFIX_RULES row $6$
test_django_pbkdf2_prefix_is_recognized     ── covers PREFIX_RULES row pbkdf2_sha256$

test_mysql5_format_is_recognized            ── covers Step 2 / _is_mysql5
test_mysql5_rejects_lowercase_body          ── covers the "be honest, don't lie" rule
test_netntlmv2_format_is_recognized         ── covers Step 2 / NetNTLMv2
test_netntlmv1_format_is_recognized         ── covers Step 2 / NetNTLMv1
test_descrypt_format_is_recognized          ── covers Step 2 / _is_descrypt

test_md5_length_returns_md5_first           ── covers Step 3 / 32 hex chars
test_sha1_length_returns_sha1_first         ── covers Step 3 / 40 hex chars
test_sha256_length_returns_sha256_first     ── covers Step 3 / 64 hex chars
test_mysql323_length_returns_mysql323_first ── covers Step 3 / 16 hex chars

test_unknown_phc_string_falls_back_to_generic
                                            ── covers Step 4

test_jwt_input_is_called_out_as_not_a_hash  ── covers Step 5
test_base64_blob_is_called_out_as_not_a_hash── covers Step 5

test_empty_input_returns_no_candidates      ── covers Step 6 (edge case)
test_garbage_returns_no_candidates          ── covers Step 6
test_input_is_trimmed_of_whitespace         ── covers the .strip() at the top

test_hash_candidate_is_frozen               ── covers the @dataclass(frozen=True)

test_every_prefix_rule_is_recognized_with_high_confidence
                                            ── meta-test: iterates over
                                            ── PREFIX_RULES and asserts every
                                            ── row produces a HIGH-confidence
                                            ── match. Keeps data and code in sync.
```

The meta-test at the bottom is the most interesting one. It's a guard against future regressions: if you add a new row to `PREFIX_RULES` and forget to update the matching logic, this test fires. The test loops over the data, not over hardcoded inputs — so the test grows automatically as the data table grows.

## 9. Why pure functions matter here

The brain (`identify()`) is what's called a **pure function**:

- Given the same input, it always returns the same output.
- It doesn't modify anything outside itself (no global variables, no files, no network).
- It doesn't depend on anything outside itself (no current time, no environment variables, no random numbers).

This sounds like a small thing. It's enormous. Pure functions are:

- **Trivially testable.** `assert identify("5f4d...") == [HashCandidate(...)]`. No mocking, no setup, no teardown.
- **Trivially parallelizable.** You could run `identify()` on a million hashes across 16 CPU cores with zero coordination, because no two calls can interfere with each other.
- **Trivially cacheable.** Same input → same output → memoize freely.
- **Trivially understandable.** You can read `identify()` in isolation. You don't have to know what state the program is in.

Most real programs can't be all-pure — they have to read files, send packets, write to databases. But you can almost always *carve out* a pure core and put a thin shell around it that does the side-effecty stuff. That's exactly the architecture here: pure brain in the middle, side-effecty CLI shell around it.

This is sometimes called the [Functional Core, Imperative Shell](https://www.destroyallsoftware.com/screencasts/catalog/functional-core-imperative-shell) pattern. It's worth learning the name because once you see it, you'll spot it everywhere.

## 10. Next up

You now know the shape: three layers, six steps, three data tables, three helpers, one `HashCandidate` record, one CLI shell. Read **[03-IMPLEMENTATION.md](./03-IMPLEMENTATION.md)** next and we'll walk every line of `hash_identifier.py` together.
