# HashBrownie

A small Python hash identifier - tells you what kind of cryptographic hash a string probably is by analyzing its shape (prefix, length, character set).

## Quick Start

```bash
# Install dependencies
just install

# Run on an MD5 hash
just run -- 5f4dcc3b5aa765d61d8327deb882cf99

# Run on bcrypt
just run -- '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQNQy.uK4Of2T7G'

# Run tests
just test

# Lint and typecheck
just lint
```

## What it does

- Identifies ~30 hash formats by prefix (bcrypt, Argon2, PBKDF2, etc.)
- Identifies common hex hashes by length (MD5, SHA-1, SHA-256, etc.)
- Recognizes NetNTLM, MySQL5, DES crypt by shape
- Distinguishes non-hashes like JWTs, Base64 blobs
- Returns ranked candidates with confidence and reasoning
- Pure analysis - no hash computation, network requests, or file I/O

## Project Structure

- `hashbrownie.py` - Main implementation
- `test_hashbrownie.py` - Test suite
- `pyproject.toml` - Dependencies and config
- `justfile` - Development commands
- `install.sh` - One-shot setup


## Screenshot

![HashBrownie in action](hashbrownie.png)
