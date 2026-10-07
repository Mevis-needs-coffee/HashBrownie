"""
©AngelaMos | 2026
hashbrownie.py

Identify what kind of hash a string is, by inspecting its shape

This is a small, educational hash identifier. It makes a best-guess
classification based on:
- prefix markers (e.g. $2b$ for bcrypt, $argon2id$ for Argon2id)
- string length (each hash algorithm produces a fixed-length output)
- character set (hex vs base64 vs crypt alphabet)

It never computes hashes, never makes network requests, and never touches
the filesystem. It's pure string analysis.
"""

import argparse
import sys
from dataclasses import dataclass
from typing import Literal

from rich.console import Console
from rich.table import Table

Confidence = Literal["high", "medium", "low"]

@dataclass(frozen=True, slots=True)
class HashCandidate:
    """One possible identification of a hash string.

    Attributes:
        algorithm: The name of the algorithm (e.g. "MD5", "bcrypt", "SHA-256")
        confidence: How confident we are in this identification
        reason: Short explanation of the evidence used
    """

    algorithm: str
    confidence: Confidence
    reason: str


PREFIX_RULES: list[tuple[str, str, str]] = [
    # Argon2 family
    ("$argon2id$", "Argon2id", "modern PHC string, the current standard"),
    ("$argon2i$", "Argon2i", "PHC string, side-channel-resistant variant"),
    ("$argon2d$", "Argon2d", "PHC string, data-dependent variant"),
    ("$argon2$", "Argon2", "generic PHC string (variant unspecified)"),
    # bcrypt and its many variants
    ("$2y$", "bcrypt", "bcrypt PHC string, 2y variant (older OpenBSD)"),
    ("$2b$", "bcrypt", "bcrypt PHC string, 2b variant (current)"),
    ("$2a$", "bcrypt", "bcrypt PHC string, 2a variant (obsolete)"),
    # SHA-crypt family
    ("$6$", "SHA-512 crypt", "Unix crypt(3) with SHA-512, very common on Linux"),
    ("$5$", "SHA-256 crypt", "Unix crypt(3) with SHA-256"),
    ("$sha512$", "SHA-512 crypt (alt)", "alternative SHA-512 crypt marker"),
    ("$sha256$", "SHA-256 crypt (alt)", "alternative SHA-256 crypt marker"),
    # MD5-crypt family
    ("$1$", "MD5 crypt", "Unix crypt(3) with MD5"),
    ("$apr1$", "Apache MD5-crypt", "Apache .htpasswd MD5 variant"),
    ("$md5$", "MD5-crypt (Sun)", "Sun MD5 crypt variant"),
    # PBKDF2 family (Django / passlib conventions)
    ("pbkdf2_sha512$", "PBKDF2-SHA512 (Django)", "Django password hash with PBKDF2-SHA512"),
    ("pbkdf2_sha256$", "PBKDF2-SHA256 (Django)", "Django password hash with PBKDF2-SHA256"),
    ("pbkdf2_sha1$", "PBKDF2-SHA1", "generic PBKDF2 with SHA-1"),
    # phpass (WordPress, phpBB)
    ("$P$", "phpass", "Portable PHP password hashing framework"),
    ("$H$", "phpass (alternative)", "phpass alternative prefix"),
    # scrypt
    ("$scrypt$", "scrypt", "PHC string for scrypt KDF"),
    # Yescrypt
    ("$y$", "yescrypt", "yescrypt KDF (modern Unix)"),
    # LDAP-style
    ("{SSHA}", "LDAP SSHA", "salted SHA-1, LDAP directory format"),
    ("{SHA}", "LDAP SHA", "unsalted SHA-1, LDAP directory format"),
    ("{SSHA512}", "LDAP SSHA512", "salted SHA-512, LDAP directory format"),
    ("{SHA512}", "LDAP SHA512", "unsalted SHA-512, LDAP directory format"),
    ("{MD5}", "LDAP MD5", "unsalted MD5, LDAP directory format"),
    ("{SMD5}", "LDAP SMD5", "salted MD5, LDAP directory format"),
]

HEX_CHARSET: frozenset[str] = frozenset("0123456789abcdefABCDEF")
_HEX_UPPER_CHARSET: frozenset[str] = frozenset("0123456789ABCDEF")


HEX_LENGTH_RULES: dict[int, list[str]] = {
    16: ["MySQL323", "CRC-64"],
    24: ["Tiger-128"],
    32: ["NTLM", "MD5", "MD4", "RIPEMD-128"],
    40: ["SHA-1", "RIPEMD-160"],
    48: ["SHA-384", "Tiger-192", "Whirlpool (older)"],
    56: ["SHA-224", "SHA3-224"],
    64: ["SHA-256", "SHA3-256", "BLAKE2s-256", "RIPEMD-256"],
    96: ["SHA-384", "SHA3-384"],
    128: ["SHA-512", "SHA3-512", "BLAKE2b-512", "Whirlpool"],
}


def _print_banner() -> None:
    """Print ASCII art banner"""
    banner_text = r"""██╗  ██╗ █████╗ ███████╗██╗  ██╗    ██████╗ ██████╗  ██████╗ ██╗    ██╗███╗   ██╗██╗███████╗
██║  ██║██╔══██╗██╔════╝██║  ██║    ██╔══██╗██╔══██╗██╔═══██╗██║    ██║████╗  ██║██║██╔════╝
███████║███████║███████╗███████║    ██████╔╝██████╔╝██║   ██║██║ █╗ ██║██╔██╗ ██║██║█████╗  
██╔══██║██╔══██║╚════██║██╔══██║    ██╔══██╗██╔══██╗██║   ██║██║███╗██║██║╚██╗██║██║██╔══╝  
██║  ██║██║  ██║███████║██║  ██║    ██████╔╝██║  ██║╚██████╔╝╚███╔███╔╝██║ ╚████║██║███████╗
╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝    ╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚══╝╚══╝ ╚═╝  ╚═══╝╚═╝╚══════╝"""
    console = Console()
    console.print(f"[bold cyan]{banner_text}[/bold cyan]\n")

_MYSQL5_HEX_BODY_LENGTH = 40
_MYSQL5_TOTAL_LENGTH = _MYSQL5_HEX_BODY_LENGTH + 1


def _is_hex(text: str) -> bool:
    """Return True iff every character in text is a hex digit and text is non-empty"""
    return bool(text) and all(c in HEX_CHARSET for c in text)


def _is_mysql5(text: str) -> bool:
    """Return True for MySQL5 password format: `*` then 40 UPPERCASE hex chars

    Example: *A3754E08D2F8D3C34F8A0A5D2B1E3D4F5A6B7C8D
    """
    if len(text) != _MYSQL5_TOTAL_LENGTH or not text.startswith("*"):
        return False
    body = text[1:]
    return all(c in _HEX_UPPER_CHARSET for c in body)


_DESCRYPT_CHARSET: frozenset[str] = frozenset(
    "./0123456789"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
)
_DESCRYPT_TOTAL_LENGTH = 13


def _is_descrypt(text: str) -> bool:
    """Return True for traditional 13-char DES crypt (legacy /etc/passwd)"""
    return (
        len(text) == _DESCRYPT_TOTAL_LENGTH
        and all(c in _DESCRYPT_CHARSET for c in text)
    )

# pylint: disable=too-many-return-statements,too-many-branches
def identify(raw_input: str) -> list[HashCandidate]:
    """Return ranked candidates for what algorithm produced `raw_input`.

    The identification is purely structural (prefix, length, charset). No
    computation of hashes occurs.

    Parameters
    ----------
    raw_input : str
        The string to identify (may contain whitespace)

    Returns
    -------
    list[HashCandidate]
        A list of candidates, ordered from most likely to less likely.
        Empty list means "could not identify".
    """

    text = raw_input.strip()

    if not text:
        return []

    # Step 1: Try prefix-based rules first (highest confidence)
    for prefix, algorithm, note in PREFIX_RULES:
        if text.startswith(prefix):
            return [
                HashCandidate(
                    algorithm=algorithm,
                    confidence="high",
                    reason=f"prefix `{prefix}` — {note}",
                )
            ]

    # Step 2: Special non-PHC shapes
    # NetNTLMv2 / NetNTLMv1
    if "::" in text and text.count(":") >= 4:
        parts = text.split(":")
        if len(parts) >= 6:
            # NetNTLMv2: parts[4] is typically a 32-hex HMAC
            if len(parts) > 4 and len(parts[4]) == 32 and _is_hex(parts[4]):
                return [
                    HashCandidate(
                        algorithm="NetNTLMv2",
                        confidence="high",
                        reason="NetNTLMv2 format — `user::domain:challenge:HMAC:blob` with 32-hex HMAC",
                    )
                ]
            # NetNTLMv1: LM response is typically 48 hex chars (often at parts[4])
            if len(parts) > 4 and len(parts[4]) == 48 and _is_hex(parts[4]):
                return [
                    HashCandidate(
                        algorithm="NetNTLMv1",
                        confidence="high",
                        reason="NetNTLMv1 format — `user::domain:challenge:LMresp:NTresp` with 48-hex LM response",
                    )
                ]
            # Also check parts[3] for some variants
            if len(parts) > 3 and len(parts[3]) == 48 and _is_hex(parts[3]):
                return [
                    HashCandidate(
                        algorithm="NetNTLMv1",
                        confidence="high",
                        reason="NetNTLMv1 format — 48-hex field in challenge/response position",
                    )
                ]


    # Pwdump/SAM format: username:rid:lmhash:nthash (e.g., user:1000:LM:NT)
    if text.count(":") >= 3:
        parts = text.split(":")
        if len(parts) >= 4:
            lm = parts[2]
            nt = parts[3]
            # NT hash is typically 32 hex (NTLM/NTHash)
            if len(nt) == 32 and _is_hex(nt):
                return [
                    HashCandidate(
                        algorithm="NTLM (NTHash)",
                        confidence="high",
                        reason="Pwdump/SAM format — NT hash (32 hex) detected",
                    )
                ]
            if len(lm) == 32 and _is_hex(lm):
                return [
                    HashCandidate(
                        algorithm="NTLM (LMHash)",
                        confidence="high",
                        reason="Pwdump/SAM format — LM hash (32 hex) detected",
                    )
                ]
    # MySQL5
    if _is_mysql5(text):
        return [
            HashCandidate(
                algorithm="MySQL5",
                confidence="high",
                reason="MySQL5 password format: `*` followed by 40 uppercase hex chars",
            )
        ]

    # DES crypt
    if _is_descrypt(text):
        return [
            HashCandidate(
                algorithm="DES crypt",
                confidence="medium",
                reason="13-char legacy DES crypt from /etc/passwd (charset `./0-9A-Za-z`)",
            )
        ]

    # Smart detection for common hash patterns
    if _is_hex(text) and len(text) == 32:
        # For standalone 32-char hex without other context, 
        # if it looks "random" it's often NTLM in security tools
        # But we need to be careful - MD5 is also common
        # Check - many NTLM hashes in practice are detected as NTLM
        # We'll prioritize NTLM for very "generic" standalone 32-hex
        return [
            HashCandidate(
                algorithm="NTLM (NTHash)",
                confidence="high",
                reason="32 hex chars — standalone NTLM hash (NTHash)",
            ),
            HashCandidate(
                algorithm="MD5",
                confidence="medium",
                reason="32 hex chars — also possible MD5",
            ),
            HashCandidate(
                algorithm="MD4",
                confidence="low",
                reason="32 hex chars — also possible MD4",
            ),
            HashCandidate(
                algorithm="RIPEMD-128",
                confidence="low",
                reason="32 hex chars — also possible RIPEMD-128",
            ),
        ]
    # Step 3: Hex + length lookup
    if _is_hex(text):
        algorithms = HEX_LENGTH_RULES.get(len(text), [])
        candidates: list[HashCandidate] = []
        for index, algorithm in enumerate(algorithms):
            confidence: Confidence = "medium" if index == 0 else "low"
            label = (
                "most likely candidate at this length"
                if index == 0
                else "also possible at this length"
            )
            candidates.append(
                HashCandidate(
                    algorithm=algorithm,
                    confidence=confidence,
                    reason=f"{len(text)} hex chars — {label}",
                )
            )
        if candidates:
            return candidates

    # Step 4: Generic PHC fallback
    if text.startswith("$"):
        rest = text[1:]
        if "$" in rest:
            algo_name = rest.split("$", 1)[0]
            if algo_name and all(c.isalnum() or c in "-_" for c in algo_name):
                return [
                    HashCandidate(
                        algorithm=f"PHC string ({algo_name})",
                        confidence="low",
                        reason=f"looks like PHC format with algorithm name `{algo_name}` (not in known rules)",
                    )
                ]

    # Step 5: Shape hints (not hashes)
    if text.startswith("eyJ"):
        return [
            HashCandidate(
                algorithm="JWT (not a hash)",
                confidence="low",
                reason="starts with `eyJ` — base64url of JSON header, looks like a JWT",
            )
        ]

    if any(c in text for c in "+/=") and len(text) > 8:
        return [
            HashCandidate(
                algorithm="Base64 blob (not a hash)",
                confidence="low",
                reason="contains `+`, `/`, or `=` — resembles Base64 encoding, not a hex/hash",
            )
        ]

    # Step 6: Give up
    return []

def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hashbrownie",
        description="Identify what kind of hash a string is by inspecting its shape",
    )
    parser.add_argument(
        "hash",
        help="The hash string to identify (paste the string directly)",
    )
    parser.add_argument(
        "--top",
        "-n",
        type=int,
        default=5,
        help="Show at most N top candidates (default: 5)",
    )
    return parser


def _render_table(raw_input: str, candidates: list[HashCandidate], console: Console) -> None:
    table = Table(
        title=f"Candidates for: {raw_input.strip()}",
        show_lines=False,
        expand=False,
    )
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


def main() -> int:
    parser = _build_argument_parser()
    args = parser.parse_args()
    console = Console()
    _print_banner()

    candidates = identify(args.hash)

    if not candidates:
        console.print(
            "[red]No identification possible.[/red] "
            "Try a longer string or check the input was pasted correctly."
        )
        return 1

    trimmed = candidates[: args.top]
    _render_table(args.hash, trimmed, console)

    if trimmed and trimmed[0].confidence == "high":
        console.print(
            "\n[dim]Next step: try the matching cracker (hashcat/john) with this algorithm.[/dim]"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
