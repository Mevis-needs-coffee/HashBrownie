# HashBrownie

![HashBrownie ASCII](hashbrownie.png)

A fast, lightweight command-line hash identifier that analyzes cryptographic hash strings and determines their likely algorithm by examining prefixes, length, and character sets.

## What is HashBrownie?

HashBrownie is a command-line tool that identifies cryptographic hash algorithms by analyzing their structure. It examines prefixes, length, and character sets to guess the hash type with confidence levels. Perfect for CTFs, penetration testing, and breach analysis - it never cracks hashes, only identifies them.

## Features

- **Smart Detection** - Identifies 30+ hash formats including bcrypt, Argon2, PBKDF2, NTLM, MySQL5, and more
- **Multiple Format Support** - Recognizes PHC-style hashes, Unix crypt formats, LDAP formats, and legacy hashes
- **Confidence Scoring** - Returns ranked candidates with high/medium/low confidence levels
- **Smart Heuristics** - Enhanced NTLM detection for standalone 32-hex hashes
- **Non-Hash Detection** - Identifies JWTs, Base64 blobs, and other non-hash strings
- **Beautiful Output** - Colorful ASCII art banner with rich-formatted tables
- **Safe & Fast** - Pure string analysis, no hash computation, network requests, or file I/O
- **Lightweight** - Single-file implementation, minimal dependencies

## Installation

### Global Installation (Recommended)

```bash
pip install git+https://github.com/Mevis-needs-coffee/HashBrownie.git
# or
uv tool install git+https://github.com/Mevis-needs-coffee/HashBrownie.git
```

### Local Development

```bash
git clone https://github.com/Mevis-needs-coffee/HashBrownie.git
cd HashBrownie
just install
```

## Quick Start

### As a global command

```bash
# Identify MD5 hash
hashbrownie 5f4dcc3b5aa765d61d8327deb882cf99

# Identify bcrypt hash (quote hashes starting with $)
hashbrownie '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQNQy.uK4Of2T7G'

# Identify Argon2 hash
hashbrownie '$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$RdescudvJCsgt3ub+b+dWRWJTmaaJObG'

# Identify NTLM hash
hashbrownie b3d4f5e0a6b7c8d9e0f1a2b7f1a8e2b9

# Show top N results
hashbrownie --top 3 <hash>
```

### For development

```bash
# Run with uv
uv run python hashbrownie.py 5f4dcc3b5aa765d61d8327deb882cf99

# Using just
just run -- 5f4dcc3b5aa765d61d8327deb882cf99

# Run tests
just test

# Lint and typecheck
just lint

# Format code
just format
```

## Screenshot

![HashBrownie in action](hashbrownie.png)

## Supported Hash Types

- **Modern PHC**: Argon2 (id/i/d), bcrypt (2a/2b/2y), scrypt, yescrypt
- **Unix crypt**: MD5-crypt, SHA-256/512 crypt, Apache MD5-crypt
- **PBKDF2**: Django PBKDF2 (SHA1/SHA256/SHA512), generic PBKDF2
- **Legacy Windows**: NTLM (NTHash/LMHash), NetNTLMv1/v2
- **Fast hashes**: MD5, MD4, SHA-1/224/256/384/512, SHA3 variants, RIPEMD variants, Whirlpool, Tiger
- **Database**: MySQL5, MySQL323
- **LDAP**: SSHA, SHA, SSHA512, SHA512, SMD5, MD5
- **Other**: phpass (WordPress/phpBB), DES crypt
- **Non-hashes**: JWT, Base64 blobs (detected and flagged)

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
