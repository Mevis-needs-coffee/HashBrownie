# Concepts

This page builds up the ideas you need to understand the code. We start from "what is a hash" and end at "here is exactly why a 32-character hex string is probably MD5." No prior security knowledge required.

## 1. What is a hash?

A **cryptographic hash function** takes any input — a single byte, a password, a 4GB video file — and produces a fixed-length output that looks like random garbage. Same input always gives the same output. Different inputs give different outputs. And critically: if you only have the output, you cannot work backwards to the input.

Picture it as a kitchen blender that only goes forwards:

```
"password"  ─────► [ MD5 blender ] ─────►  5f4dcc3b5aa765d61d8327deb882cf99
"hello"     ─────► [ MD5 blender ] ─────►  5d41402abc4b2a76b9719d911017c592
"hello!"    ─────► [ MD5 blender ] ─────►  d9014c4624844aa5bac314773d6b689a
                          │
                          └─ change ONE character → totally different output
```

A few properties that fall out of this:

- **Deterministic.** Same input, same output, every single time. This is the whole reason hashes are useful — you can store the hash of a password, and when someone logs in you re-hash what they typed and compare.
- **Fixed-length output.** Whether you hash `"a"` or the entire Bible, MD5 always produces 32 hex characters. SHA-256 always produces 64. This length is the first big clue we use to identify which algorithm was used.
- **One-way.** You can go from password → hash, but not from hash → password. There is no "un-hash" button. The only way to figure out which password produced a hash is to *guess passwords and hash them yourself* until you get a match. That guessing is what hashcat does.
- **Avalanche effect.** Change one letter of the input and the entire output changes. `"password"` and `"Password"` produce hashes that share zero characters.

If you want to play with this for yourself, in a Python REPL (`uv run python`):

```python
>>> import hashlib
>>> hashlib.md5(b"password").hexdigest()
'5f4dcc3b5aa765d61d8327deb882cf99'
>>> hashlib.md5(b"Password").hexdigest()
'dc647eb65e6711e155375218212b3964'
```

The `b"..."` syntax means "this is bytes, not text" — hash functions work on raw bytes, not characters. Don't worry about that distinction yet; just notice that one letter change produced a completely different hash.

## 2. Why hashes exist (the password storage problem)

Imagine you run a website. Users sign up with a password. The naive thing to do is store passwords in your database directly:

```
+----------+------------+
| username | password   |
+----------+------------+
| alice    | hunter2    |
| bob      | letmein    |
+----------+------------+
```

This is a catastrophe waiting to happen. The moment somebody breaches your database — and someone always eventually does — every user is exposed. Worse, since people [reuse passwords across sites](https://www.security.org/digital-safety/password-reuse-statistics/), the attacker now has the keys to Alice's bank, Alice's email, and Alice's Netflix.

The fix is to never store the password itself. Store its hash:

```
+----------+----------------------------------+
| username | password_hash                    |
+----------+----------------------------------+
| alice    | 5f4dcc3b5aa765d61d8327deb882cf99 |  ← MD5("hunter2")... if it were
| bob      | 0d107d09f5bbe40cade3de5c71e9e9b7 |     "password" (it isn't)
+----------+----------------------------------+
```

When Alice logs in, you hash what she just typed and compare it to the stored hash. If they match, she gets in. You never knew her password and you never have to.

The attacker who steals this database now has hashes, not passwords. They have to *guess* every password by hashing candidate passwords and comparing. With a fast hash like MD5, a modern GPU can try billions of guesses per second. With a slow hash like bcrypt, it can try only thousands. That's the entire reason modern systems use slow hashes — not because they're "more secure" in some abstract way, but because they make guessing *expensive*.

## 3. Real breaches that turned on hash identification

Identifying the hash format is the *first move* in every password-leak story. Until you know what algorithm made the hashes, nothing else happens.

**[2012 LinkedIn breach](https://en.wikipedia.org/wiki/2012_LinkedIn_hack)** — 6.5 million unsalted SHA-1 hashes leaked. Forty hex characters each. Researchers identified the format in seconds, then cracked 90% of the hashes in 72 hours because SHA-1 is fast and the passwords had no salt (more on salt below). LinkedIn later admitted [117 million more accounts](https://www.theguardian.com/technology/2016/may/19/linkedin-2012-data-breach-hack-117-million-email-password-details) were exposed than originally disclosed.

**[2013 Adobe breach](https://krebsonsecurity.com/2013/11/adobe-breach-impacted-at-least-38-million-users/)** — 153 million accounts, with passwords stored using 3DES encryption (not even hashing) and no unique salts. The lack of unique salts meant identical passwords produced identical ciphertext. Researchers could see, just by looking at the dump, which 1.9 million accounts shared the password `123456`.

**[2016 Yahoo breach](https://en.wikipedia.org/wiki/Yahoo!_data_breaches)** — 3 billion accounts. Some hashed with MD5 (catastrophic), some with bcrypt (much better). The mixed format made identification the first task before any defense analysis could proceed.

**[2019 Collection #1](https://www.troyhunt.com/the-773-million-record-collection-1-data-reach/)** — 773 million email/password pairs aggregated from past breaches. Researchers had to sort which hashes were which algorithm before anything else.

The pattern is the same every time: dump appears → identify the algorithm → decide whether cracking is feasible → reach for hashcat.

## 4. The three signals a hash leaks about itself

This is the heart of the tool. A hash string carries up to three clues about its own origin: its **prefix**, its **length**, and its **character set**. We use these in order, strongest first.

### Signal 1: prefix (the strongest clue)

Modern password hashes use a self-describing format called **PHC string format** (PHC stands for "Password Hashing Competition," the contest that gave us Argon2 in 2015). A PHC string starts with a marker that announces the algorithm:

```
$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$RdescudvJCsgt3ub+b+dWRWJTmaaJObG
^^^^^^^^^^
 │
 └─ "I am an Argon2id hash. You don't have to guess."
```

```
$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQNQy.uK4Of2T7G.VHvgvWK
^^^^
 │
 └─ "I am a bcrypt hash, variant 2b, cost factor 12."
```

When a hash announces itself like this, identification is essentially free — you just compare prefixes. The tool reports **HIGH confidence** for prefix matches because the hash literally told you what it is. The PHC spec is documented [here](https://github.com/P-H-C/phc-string-format/blob/master/phc-sf-spec.md) if you want the full grammar.

Old hashes do *not* do this. MD5 and SHA-1 just give you the raw hex digest with no prefix. Which is why the modern shift to PHC was a big deal — it makes the system self-documenting.

Here's a non-exhaustive cheat sheet of common prefixes. The full table is in `hash_identifier.py` under `PREFIX_RULES`:

| Prefix             | Algorithm           | Where you see it                                |
| ------------------ | ------------------- | ----------------------------------------------- |
| `$argon2id$`       | Argon2id            | Modern web apps, the current gold standard      |
| `$2b$`             | bcrypt              | Workhorse for the past 15 years                 |
| `$6$`              | SHA-512 crypt       | `/etc/shadow` on most Linux distros             |
| `$apr1$`           | Apache MD5-crypt    | `.htpasswd` files (Apache basic auth)           |
| `$P$`              | phpass              | WordPress and old phpBB forums                  |
| `pbkdf2_sha256$`   | Django PBKDF2       | Default for Django web apps                     |
| `{SSHA}`           | LDAP salted SHA-1   | LDAP directory passwords                        |

### Signal 2: length (the second-strongest clue)

Hash functions emit fixed-length output. If you see no prefix but you have 64 hex characters, you can be confident it came from one of the 256-bit hash family (SHA-256, SHA3-256, BLAKE2s-256, RIPEMD-256). Each algorithm always emits the same number of bytes:

```
algorithm        bytes      hex chars
─────────────────────────────────────
MD5              16           32
SHA-1            20           40
SHA-224          28           56
SHA-256          32           64
SHA-384          48           96
SHA-512          64          128
```

The reason the number of hex characters is double the number of bytes: each byte is 8 bits, but a hex character represents only 4 bits (one of 16 possible values: `0-9a-f`). So you need two hex characters per byte.

Length narrows the field but rarely picks a unique winner. 32 hex characters could be MD5, NTLM, MD4, or RIPEMD-128 — they all produce 128 bits of output. So when the tool matches on length, it reports **MEDIUM confidence** for the most likely algorithm at that length and **LOW** for the rest. "Most likely" means "most common in the wild in 2026" — MD5 vastly outranks RIPEMD-128.

### Signal 3: charset (used as a sanity check)

The character set of the hash narrows things further. Three common alphabets show up:

- **Hex:** only `0-9a-f` (or `0-9A-F` if uppercase). Used by raw MD5, SHA-family, NTLM, etc.
- **Base64-ish:** `0-9A-Za-z+/=`. Used by LDAP and some Java password formats.
- **crypt(3) base64:** a peculiar alphabet `./0-9A-Za-z` (note the `.` and `/` at the start, no `=` for padding). Used by bcrypt and the old Unix crypt formats.

A string with `+` in it is *not* a hex hash. A string with `*` followed by 40 uppercase hex characters is almost certainly MySQL5 (and only MySQL5 — because MySQL prints its hashes using the `%02X` C format specifier, which is uppercase-only).

Charset alone rarely identifies anything, but it's the tiebreaker that lets us *rule things out*. For example, the helper `_is_mysql5` in the code refuses to match if the body is lowercase, because real MySQL5 output is always uppercase. Better to say "I don't know" than to lie with confidence.

## 5. Salts (a quick detour)

You'll see the word **salt** all over the place when you read about password hashing. A salt is a unique random string that you mix into the password before hashing, then store alongside the hash:

```
hash = bcrypt("hunter2" + random_salt_for_alice)
```

The point of a salt is to make every user's hash *different*, even if two users picked the same password. Without salts, you can sort the database by hash column, count duplicates, and immediately learn which password is most popular (this is exactly how researchers learned `123456` was Adobe's most popular password — no cracking required).

Salts also defeat **rainbow tables**: precomputed lookup tables that map `hash → password` for billions of common passwords. With a unique salt per user, every entry in the rainbow table would have to be recomputed for *every salt*, which is infeasible.

A PHC string like `$2b$12$EixZaYVK1fsbw1ZfbX3OXe...` contains the salt right there in the string (the `EixZaYVK1fsbw1ZfbX3OXe` part). That's not a security problem — the salt is supposed to be public. Its job is to make every hash unique, not to be secret.

## 6. Why identification has to come first

Cracking tools don't auto-detect the algorithm — they need you to tell them.

```bash
# Hashcat, mode 0 (MD5):
hashcat -m 0 -a 0 5f4dcc3b5aa765d61d8327deb882cf99 wordlist.txt

# Hashcat, mode 3200 (bcrypt):
hashcat -m 3200 -a 0 '$2b$12$EixZaY...' wordlist.txt

# John the Ripper, --format=raw-md5:
john --format=raw-md5 --wordlist=wordlist.txt hashes.txt
```

Pick the wrong mode and hashcat will sit there comparing your bcrypt hash against MD5 outputs forever and finding nothing. So *before* you crack, you identify.

This is why a tool like the one in this project (and the older [`hashid`](https://github.com/psypanda/hashID) and [`hash-identifier`](https://github.com/blackploit/hash-identifier) projects it's inspired by) exists. It is the first step. Our tool is a beginner-friendly clone of that idea, written so you can read every line and understand every decision.

## 7. The tradeoff this tool is making

We could theoretically achieve higher accuracy by trying every algorithm and computing diagnostics. We don't. We make decisions from *string shape alone*:

- We never run any hash function.
- We never make network requests.
- We never touch the filesystem.
- We never call any external tool.

This makes the tool **fast** (instant), **safe** (impossible to leak data), and **trivially testable** (every test is "given input X, expect output Y"). It's a pure function, in the mathematical sense — same input always gives same output, no side effects.

The cost is that we sometimes report multiple candidates with MEDIUM/LOW confidence. We could in principle pick a winner if we tried each algorithm against a known wordlist — but that's a different tool. That tool is the cracker, and it lives in `PROJECTS/beginner/hash-cracker`. Our tool's whole job is to point you at the *right cracker mode* in the first place.

## 8. What the tool will and will not do

| Will                                                  | Will not                                            |
| ----------------------------------------------------- | --------------------------------------------------- |
| Identify ~30 hash formats by prefix                   | Crack any hash                                      |
| Identify common hex hashes by length                  | Compute hashes for you                              |
| Recognize MySQL5, NetNTLM, DES crypt by shape         | Call hashcat or john for you                        |
| Tell you "that's a JWT" or "that's base64, not a hash"| Tell you the password                               |
| Print ranked candidates with confidence and reasoning | Make network requests                               |
| Run as a one-shot CLI in milliseconds                 | Touch the filesystem                                |

## 9. Where to go from here

Now that you know *what* the tool is doing and *why*, read **[02-ARCHITECTURE.md](./02-ARCHITECTURE.md)** to see how the code is structured into a six-step decision pipeline. Then **[03-IMPLEMENTATION.md](./03-IMPLEMENTATION.md)** walks the actual Python file with you, function by function.
