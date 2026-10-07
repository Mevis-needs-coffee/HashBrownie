"""
©AngelaMos | 2026
test_hashbrownie.py

Tests for hashbrownie.py - mirrors the behavior described in the project spec.
"""

import pytest
from rich.console import Console

from hashbrownie import (
    PREFIX_RULES,
    HashCandidate,
    _build_argument_parser,
    _is_descrypt,
    _is_hex,
    _is_mysql5,
    _render_table,
    identify,
)


def test_argon2id_prefix_is_recognized():
    text = "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$RdescudvJCsgt3ub+b+dWRWJTmaaJObG"
    candidates = identify(text)
    assert candidates
    assert candidates[0].algorithm == "Argon2id"
    assert candidates[0].confidence == "high"
    assert "prefix" in candidates[0].reason


def test_bcrypt_prefix_is_recognized():
    text = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQNQy.uK4Of2T7G.VHvgvWK"
    candidates = identify(text)
    assert candidates
    assert candidates[0].algorithm == "bcrypt"
    assert candidates[0].confidence == "high"


def test_apr1_prefix_is_recognized():
    text = "$apr1$J4D.4z8g$hR9Llj3hUZp8h7c5j1kS90"
    candidates = identify(text)
    assert candidates
    assert candidates[0].algorithm == "Apache MD5-crypt"
    assert candidates[0].confidence == "high"


def test_sha512_crypt_prefix_is_recognized():
    text = "$6$rounds=5000$abcdefghijklmnopqrst$XyZ1234567890abcdef..."
    candidates = identify(text)
    assert candidates
    assert candidates[0].algorithm == "SHA-512 crypt"
    assert candidates[0].confidence == "high"


def test_django_pbkdf2_prefix_is_recognized():
    text = "pbkdf2_sha256$260000$abcd1234$secrethere..."
    candidates = identify(text)
    assert candidates
    assert candidates[0].algorithm == "PBKDF2-SHA256 (Django)"
    assert candidates[0].confidence == "high"


def test_mysql5_format_is_recognized():
    text = "*A3754E08D2F8D3C34F8A0A5D2B1E3D4F5A6B7C8D"  # 40 uppercase hex
    candidates = identify(text)
    assert candidates
    assert candidates[0].algorithm == "MySQL5"
    assert candidates[0].confidence == "high"


def test_mysql5_rejects_lowercase_body():
    text = "*a3754e08d2f8d3c34f8a0a5d2b1e3d4f5a6b7c8d"
    candidates = identify(text)
    # Should NOT be recognized as MySQL5 (requires uppercase hex body)
    assert candidates[0].algorithm != "MySQL5" if candidates else True


def test_netntlmv2_format_is_recognized():
    text = "user::DOMAIN:1122334455667788:9B7C3D2A1E5F809A1122334455667789:010100000000000080..."
    candidates = identify(text)
    assert candidates
    assert candidates[0].algorithm == "NetNTLMv2"
    assert candidates[0].confidence == "high"


def test_netntlmv1_format_is_recognized():
    lm = "A" * 48  # 48 hex chars
    nt = "B" * 48  # 48 hex chars
    text = f"user::DOMAIN:1122334455667788:{lm}:{nt}"
    candidates = identify(text)
    assert candidates
    assert candidates[0].algorithm == "NetNTLMv1"
    assert candidates[0].confidence == "high"


def test_descrypt_format_is_recognized():
    text = "abc123def4567"  # 13 chars from ./0-9A-Za-z
    candidates = identify(text)
    assert candidates
    assert candidates[0].algorithm == "DES crypt"
    assert candidates[0].confidence == "medium"


def test_md5_length_returns_md5_first():
    text = "5f4dcc3b5aa765d61d8327deb882cf99"  # 32 hex
    candidates = identify(text)
    assert candidates
    assert candidates[0].algorithm == "NTLM (NTHash)" or candidates[0].algorithm == "MD5"
    assert candidates[0].confidence in ("high", "medium")


def test_sha1_length_returns_sha1_first():
    text = "a" * 40  # 40 hex
    candidates = identify(text)
    assert candidates
    assert candidates[0].algorithm == "SHA-1"
    assert candidates[0].confidence == "medium"


def test_sha256_length_returns_sha256_first():
    text = "a" * 64  # 64 hex
    candidates = identify(text)
    assert candidates
    assert candidates[0].algorithm == "SHA-256"
    assert candidates[0].confidence == "medium"


def test_unknown_phc_string_falls_back_to_generic():
    text = "$weirdalgo$somethinghere"
    candidates = identify(text)
    assert candidates
    assert "PHC string" in candidates[0].algorithm
    assert candidates[0].confidence == "low"


def test_jwt_input_is_called_out_as_not_a_hash():
    text = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    candidates = identify(text)
    assert candidates
    assert "JWT" in candidates[0].algorithm
    assert candidates[0].confidence == "low"


def test_base64_blob_is_called_out_as_not_a_hash():
    text = "dGVzdHN0cmluZ2hlcmV3aXRoPj8rLw=="  # base64 with +/=
    candidates = identify(text)
    assert candidates
    assert "Base64" in candidates[0].algorithm
    assert candidates[0].confidence == "low"


def test_empty_input_returns_no_candidates():
    candidates = identify("")
    assert candidates == []


def test_garbage_returns_no_candidates():
    candidates = identify("helloworldnotahash")
    assert candidates == []


def test_input_is_trimmed_of_whitespace():
    text = "  5f4dcc3b5aa765d61d8327deb882cf99  "
    candidates = identify(text)
    assert candidates
    assert candidates[0].algorithm in ("MD5", "NTLM", "NTLM (NTHash)")


def test_hash_candidate_is_frozen():
    c = HashCandidate(algorithm="MD5", confidence="medium", reason="test")
    with pytest.raises(Exception):  # FrozenInstanceError
        c.algorithm = "SHA-1"


def test_every_prefix_rule_is_recognized_with_high_confidence():
    for prefix, algorithm, note in PREFIX_RULES:
        # Build a minimal plausible string that starts with prefix
        if prefix.startswith("$") and prefix.endswith("$"):
            test_str = prefix + "dummydata"
        elif prefix.startswith("{"):
            test_str = prefix + "abc123"
        else:
            test_str = prefix + "moredata"
        candidates = identify(test_str)
        assert candidates, f"No match for prefix {prefix}"
        assert candidates[0].algorithm == algorithm, f"Wrong algo for {prefix}: {candidates[0].algorithm}"
        assert candidates[0].confidence == "high", f"Wrong confidence for {prefix}: {candidates[0].confidence}"
