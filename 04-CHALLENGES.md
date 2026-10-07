# Challenges

You've read the code. You know what every line does. Now the only way to make this knowledge actually yours is to *change* the code. This page is a ladder of extensions, easiest to hardest. Don't skip rungs — each one teaches a thing that the next one assumes.

For every challenge: **write the test first.** Then make the test pass. That's the rhythm professional developers actually use. The test file already shows you the pattern — copy one of the existing `test_*` functions, change the input and expected output, watch it fail, then change the code until it passes.

## Tier 1 — get comfortable

### Challenge 1.1: Add a new prefix rule

`PREFIX_RULES` has ~25 entries today. There are dozens more. Pick one from the list below and add it:

| Prefix       | Algorithm          | Where it comes from                       |
| ------------ | ------------------ | ----------------------------------------- |
| `$pbkdf2$`   | PBKDF2-SHA1 (Atlassian) | Older Atlassian / Jira hashes        |
| `$ml$`       | macOS / iCloud Keychain | Apple PBKDF2-SHA512                  |
| `{x-pbkdf2}` | PBKDF2 (some Atlassian)  | LDAP-style wrapper                  |
| `$sha1$`     | sha1crypt          | A rare crypt(3) variant                   |
| `$md5,`      | Solaris MD5 crypt  | Note the comma instead of `$` — be careful |

**Steps:**

1. Open `hash_identifier.py`. Add one row to `PREFIX_RULES`.
2. Open `test_hash_identifier.py`. Copy an existing prefix test (e.g. `test_argon2id_prefix_is_recognized`). Rename it. Replace the input string with a sample of your new prefix. Update the assertion.
3. Run `just test`. The new test should pass. The meta-test `test_every_prefix_rule_is_recognized_with_high_confidence` should also still pass.
4. Run the tool on your new input: `just run -- '$pbkdf2$...'`. Confirm the new algorithm shows up.

**What you learn:** the table-driven design pays off — you wrote zero new logic, just data. That's the goal.

### Challenge 1.2: Add a length to HEX_LENGTH_RULES

There's no rule for 24 hex chars (96 bits) right now. That length is rare but `Tiger-128` and some old custom hashes produce it.

1. Add `24: ["Tiger-128"]` to `HEX_LENGTH_RULES`.
2. Write a test (`test_tiger128_length_returns_tiger128`).
3. Run `just test`.

**Twist:** what should happen if someone passes a 24-character string that *isn't* hex? The existing `_is_hex` check should handle it. Read step 3 of `identify()` and confirm.

### Challenge 1.3: Add a `--json` output mode

Right now the CLI only prints a colored table. Add a `--json` flag that prints the candidates as JSON instead. JSON is what every other tool will want to consume — your output becomes machine-readable.

**Hints:**

- `argparse` supports boolean flags via `action="store_true"`. Add `parser.add_argument("--json", action="store_true", help="...")`.
- The standard library `json` module has `json.dumps(data)`.
- `HashCandidate` is a dataclass, so `dataclasses.asdict(candidate)` converts it to a plain dict that `json.dumps` can serialize.
- Test it: `just run -- --json 5f4d...` should output a JSON array.

**Twist:** make the JSON include a top-level `input` field with the original string, so a downstream tool knows what was identified. And pretty-print with `indent=2`.

## Tier 2 — actually new behavior

### Challenge 2.1: Read hashes from a file or stdin

Right now the tool takes one hash per invocation. Real workflows have files with millions of hashes. Extend the CLI so it can take input from a file (`--file hashes.txt`) or from standard input when no positional argument is given (so `cat hashes.txt | hashid` works).

**Hints:**

- Make the positional `hash` argument optional with `nargs="?"`.
- Add `--file` with `type=argparse.FileType("r")`.
- Use `sys.stdin.read()` (or iterate `sys.stdin` line-by-line) when both are missing.
- The output for batch input should be different — probably one line per input, not a colored table for each. Decide what format makes sense and document it.

**Twist:** what should happen if the same input appears 1000 times in the file? Should you re-run `identify()` each time, or cache results? Try both and measure with `just run` on a file of 1M repeated hashes. (Bigger lesson: caching is only a win when the function is pure. Ours is.)

### Challenge 2.2: Add hashcat-mode hints

Hashcat assigns a numeric mode to every algorithm: 0 for MD5, 100 for SHA-1, 3200 for bcrypt, etc. The full list is documented at [hashcat.net/wiki/doku.php?id=example_hashes](https://hashcat.net/wiki/doku.php?id=example_hashes).

Extend `HashCandidate` with an optional `hashcat_mode: int | None` field. When you build a candidate, look up its mode (you'll need a `dict[str, int]` mapping algorithm name → mode) and fill it in.

Then print the mode in the table, and update the "next step" nudge at the end of `main()` to suggest the exact hashcat command:

```
Next step: hashcat -m 3200 -a 0 '$2b$12$EixZ...' wordlist.txt
```

**Hints:**

- `Optional` fields on a dataclass need defaults: `hashcat_mode: int | None = None`.
- The mode lookup is another data table — keep the data-driven design.
- John the Ripper uses different names (e.g. `bcrypt`, `raw-md5`). Add those too if you're feeling generous.

### Challenge 2.3: Recognize more "not a hash" inputs

Step 5 only catches JWTs and base64 blobs. Many other things get pasted into hash identifiers by accident. Add detectors for:

- **URLs** — start with `http://` or `https://`. Tell the user it's a URL.
- **Hex with `0x` prefix** — Ethereum addresses, memory addresses. Tell the user.
- **Base58** — used by Bitcoin addresses and IPFS hashes. Alphabet is `123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz` (no `0`, `O`, `I`, `l`).
- **Base32** — uppercase letters + digits 2-7. Used by some Tor onion addresses and TOTP secrets.

Each one is a new branch in step 5, returning a LOW-confidence "not a hash" candidate. Be honest with the confidence — these are *shape* hints, not certainties.

## Tier 3 — extend the model

### Challenge 3.1: Multi-hash detection in one string

Some breach dumps contain *combined* records like `user:hash:salt`. Real workflows often have to split these into the constituent parts before identification. Add a `--split` mode that:

1. Takes a string with colon-separated fields.
2. Identifies each field independently.
3. Prints a table showing which field is what (username, hash, salt, garbage).

**Hints:**

- This is mostly heuristics. A field that's all letters is probably a username; a field that matches a hash rule is probably the hash; a short random-looking field could be a salt.
- Pull the field-classification logic out of `identify()` — it's a new layer on top.
- Test on real-looking lines like `alice:$2b$12$EixZ...`, `bob:5f4dcc3b5aa765d61d8327deb882cf99:salt123`.

### Challenge 3.2: Confidence rebalancing with evidence weights

Right now `confidence` is a single value: high, medium, or low. But evidence is more nuanced. A 32-hex string that *also* contains no characters above 'f' is "very likely hex." A 13-character string from the DES charset is "13-char DES-compatible" but the same characters could appear in many short strings.

Replace `confidence: Literal["high", "medium", "low"]` with `confidence_score: float` in the range 0.0–1.0. Compute the score from multiple evidence weights:

- prefix match: 0.95
- special shape match: 0.85
- length match (1st candidate): 0.55
- length match (Nth candidate): 0.55 / N
- charset match: small additive bonus
- not-a-hash hint: 0.30

Then in the CLI, map score back to a color (>0.8 green, 0.5–0.8 yellow, <0.5 cyan) for display. The user still sees three buckets; the internal model gets richer.

**What you learn:** how scoring systems work under the hood. This is the same idea as Bayesian spam classifiers, search relevance ranking, and antivirus heuristics — combine multiple weak signals into one numeric score, then bucket for display.

### Challenge 3.3: Suggest the *crack difficulty* alongside the algorithm

Once you know the algorithm, you also implicitly know how hard the hash is to crack. MD5 cracks at billions of guesses per second on a modern GPU; bcrypt at thousands. Argon2id with strong parameters might be hundreds.

Add a `crack_difficulty: Literal["trivial", "moderate", "hard", "very_hard"]` field to `HashCandidate`, filled in from a per-algorithm table. Print it in the output table.

**Twist:** for parameterized hashes (bcrypt cost factor, Argon2 memory/time), parse the parameters out of the PHC string. A bcrypt hash with cost factor 4 is much weaker than one with cost factor 14. Have your output reflect that:

```
algorithm  difficulty  reason
─────────  ──────────  ──────────────────────────────────────────
bcrypt     moderate    cost=4 — much weaker than the default 12
bcrypt     hard        cost=12 — the modern default
bcrypt     very_hard   cost=14 — paranoid setting
```

## Tier 4 — make it real

### Challenge 4.1: Run identification against a real breach dump

The [HaveIBeenPwned](https://haveibeenpwned.com/Passwords) password file is a publicly-distributed list of ~1 billion SHA-1 hashes of leaked passwords, available as a torrent. (Use the **SHA-1** version, not the NTLM version — and use it only for educational analysis; don't try to "crack" it for any malicious purpose. The hashes themselves are public.)

Run your tool against the first 1000 lines. Confirm it identifies them all as SHA-1 (40 hex chars). Measure throughput: how many hashes per second can your tool process? Where's the bottleneck?

**Bigger lesson:** the brain is microseconds; the bottleneck is the CLI printing. To process millions of hashes you'd skip `rich` and stream JSON to stdout. That's a different program for a different use case.

### Challenge 4.2: Compare to `hashid` and `name-that-hash`

Two existing tools do roughly what ours does:

- [hashid](https://github.com/psypanda/hashID) — the classic, ~10 years old, written in pure Python.
- [name-that-hash](https://github.com/HashPals/Name-That-Hash) — newer, more thorough, more aggressive about guessing.

Run all three on the same inputs. Compare:

- Which detects more formats?
- Which has the best false-positive rate (says "definitely SHA-256" on garbage that isn't)?
- Which is fastest on a batch input?

Write up your findings. This is exactly the kind of work security researchers do when picking a tool for production use.

### Challenge 4.3: Wrap it into a `pre-commit` hook

`pre-commit` is a tool that runs checks before you `git commit`. People sometimes accidentally commit password hashes to repos (extremely bad). Build a `pre-commit` hook that runs your identifier on every changed file and refuses the commit if it finds anything that looks like a real hash.

**Hints:**

- Read [pre-commit's hook tutorial](https://pre-commit.com/#new-hooks).
- For each line of each changed file, run `identify(line)`. If the top candidate is HIGH confidence and isn't a generic-PHC or not-a-hash, refuse.
- Exit code 1 = block the commit; exit code 0 = allow it.
- Add allowlist comments like `# pragma: allow-hash` so that legitimate test fixtures don't get blocked.

This is the kind of "small tool, real impact" project that ends up in real security teams' toolchains.

## Tier 5 — break the model

### Challenge 5.1: Why is this a hard problem?

So far we've matched on *structure*: prefix, length, charset. But the model has limits. Consider:

- Two different algorithms producing the same length output (MD5 vs NTLM at 32 hex chars). We *can't* distinguish them from structure alone.
- An algorithm whose output is sometimes uppercase and sometimes lowercase (different libraries produce different cases for the same algo).
- A truncated SHA-256 — someone took the first 32 hex chars of a SHA-256 output and called it a "hash." We'd identify it as MD5.

Write a short document (`docs/limitations.md`) listing every case where the tool *cannot* distinguish two formats and explain why. This is the kind of honesty good security tools document up-front. Don't pretend the tool is more capable than it is.

### Challenge 5.2: Probabilistic identification with a ML classifier

The structural approach is interpretable but limited. The opposite extreme is to train a classifier on labeled hashes and let it learn the structure for you.

Build a tiny experiment:

1. Generate 100k labeled training samples: known passwords hashed with each algorithm. (Use Python's `hashlib`, `bcrypt`, `argon2-cffi`, etc.)
2. Train a simple classifier — `sklearn.linear_model.LogisticRegression` with character-n-gram features works fine for this.
3. Run the classifier on held-out test samples. Measure accuracy.
4. Compare to your rule-based identifier on the same test set.

**What you'll learn:** the rule-based system probably wins on common formats (it has all the structural priors baked in) and the ML model probably wins on unusual cases (it picks up patterns you didn't think to encode). Real-world tools combine both — rules first, ML for tie-breaking. This is how spam classifiers, web application firewalls, and antivirus engines actually work.

> **Don't run any of these challenges on real user data without permission.** The challenges assume publicly-released breach archives, your own test data, or CTF inputs. Identifying hashes from data you don't have rights to is a different conversation and outside the scope of this project.

## Where to go after the challenges

If you finished tier 4 or 5, you should now have a strong feel for the *whole loop*: read code → understand → modify → test → measure → document. That loop is the entire job of a security engineer. The specific topic doesn't matter much — you'd do the same loop for a port scanner, a fuzzer, a SIEM rule, or a vulnerability scanner.

When you're ready for more:

- **`PROJECTS/beginner/hash-cracker`** — the natural sibling to this tool. You learned to identify a hash; that project teaches you how to crack one.
- **`PROJECTS/foundations/http-headers-scanner`** — another foundations-tier project, single-file Python. Slightly more involved I/O (it makes a network request) but the same architectural shape.
- **`PROJECTS/foundations/password-manager`** — the hardest foundations project. Encryption, key derivation, and a real on-disk vault. Read [01-CONCEPTS.md](./01-CONCEPTS.md) first to understand why Argon2id is the right choice for the key derivation step.
- **`PROJECTS/beginner/simple-port-scanner`** — once you've absorbed the patterns here, port scanning is a natural next step. Sockets, concurrency, and timing all show up.

Good luck. Read everything. Write code. Break it. Fix it. That's how you learn this.
