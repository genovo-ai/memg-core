"""
HRID generator and parser for MEMG Core.

Format: {TYPE_UPPER}_{AAA000}
- TYPE: uppercase alphanumeric type name (no spaces)
- AAA: base26 letters A–Z (wraps after ZZZ)
- 000–999: numeric suffix
"""

from __future__ import annotations

import re

# Matches HRIDs like TASK_AAA001, NOTE_ZZZ999
_HRID_RE = re.compile(r"^(?P<type>[A-Z0-9]+)_(?P<alpha>[A-Z]{3})(?P<num>\d{3})$")

# Monotonic counters per type (in-memory; persistent store should be used in production)
_COUNTERS: dict[str, tuple[int, int]] = {}  # {type: (alpha_idx, num)}


def _alpha_to_idx(alpha: str) -> int:
    """AAA -> 0, AAB -> 1, ..., ZZZ -> 17575."""
    idx = 0
    for char in alpha:
        idx = idx * 26 + (ord(char) - ord("A"))
    return idx


def _idx_to_alpha(idx: int) -> str:
    """0 -> AAA, 1 -> AAB, ..., 17575 -> ZZZ."""
    chars = []
    for _ in range(3):
        chars.append(chr(ord("A") + idx % 26))
        idx //= 26
    return "".join(reversed(chars))


def generate_hrid(type_name: str) -> str:
    """Generate the next HRID for the given type."""
    t = type_name.strip().upper()
    alpha_idx, num = _COUNTERS.get(t, (0, -1))
    num += 1
    if num > 999:
        num = 0
        alpha_idx += 1
        if alpha_idx > 26**3 - 1:
            raise ValueError(f"HRID space exhausted for type {t}")
    _COUNTERS[t] = (alpha_idx, num)
    return f"{t}_{_idx_to_alpha(alpha_idx)}{num:03d}"


def parse_hrid(hrid: str) -> tuple[str, str, int]:
    """Parse HRID into (type, alpha, num)."""
    m = _HRID_RE.match(hrid.strip().upper())
    if not m:
        raise ValueError(f"Invalid HRID format: {hrid}")
    return m.group("type"), m.group("alpha"), int(m.group("num"))


def reset_counters() -> None:
    """Reset in-memory counters (mainly for testing)."""
    _COUNTERS.clear()


def _type_key(t: str) -> int:
    """
    Deterministic numeric key for type names to enable cross-type ordering.
    Encodes up to the first 8 chars in base-37 (A–Z=1–26, 0–9=27–36).
    """
    t = t.upper()
    key = 0
    for c in t[:8]:
        if "A" <= c <= "Z":
            v = 1 + (ord(c) - ord("A"))
        elif "0" <= c <= "9":
            v = 27 + (ord(c) - ord("0"))
        else:
            v = 0
        key = key * 37 + v
    return key


def hrid_to_index(hrid: str) -> int:
    """Convert HRID into a single integer index for ordering across types."""
    type_, alpha, num = parse_hrid(hrid)
    intra = _alpha_to_idx(alpha) * 1000 + num  # 0 .. 17,575,999  (needs 25 bits)
    return (_type_key(type_) << 25) | intra
