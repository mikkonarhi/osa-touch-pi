"""Parsers for AQ6315 talker (output) data, per manual Table 9-4 (pages 9-37 .. 9-47).

Default delimiters after power-on: string delimiter ',' (SD0), block delimiter CRLF+EOI (BD0).
With header output on (HD1) each reply starts with an alphabetic header such as "DBM", "LNW", "WMKR".
"""
from __future__ import annotations

import re
from typing import Optional

from .errors import ParseError

_NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][-+]?\d+)?")
_SPLIT = re.compile(r"[,\r\n]+")


def numbers(text: str) -> list[float]:
    """All numbers in a reply, ignoring alphabetic headers."""
    return [float(m.group()) for m in _NUM.finditer(text)]


def first_number(text: str) -> float:
    m = _NUM.search(text)
    if not m:
        raise ParseError(f"no number in reply {text!r}")
    return float(m.group())


def split_fields(text: str) -> list[str]:
    return [f.strip() for f in _SPLIT.split(text.strip()) if f.strip()]


def parse_trace(text: str, expect_header_count: bool = True) -> list[float]:
    """LDATAx / WDATAx reply -> list of values.

    Reply layout: [header] <count> , v1 , v2 , ... (BD).  The leading count is removed and
    checked against the number of values received.
    """
    fields = split_fields(text)
    if fields and re.match(r"^[A-Za-z]+$", fields[0]):          # header alone in first field (SD=CRLF)
        fields = fields[1:]
    vals: list[float] = []
    for f in fields:
        f = re.sub(r"^[A-Za-z]+\s*", "", f)                      # header glued to first value
        if not f:
            continue
        try:
            vals.append(float(f))
        except ValueError as e:
            raise ParseError(f"bad trace field {f!r}") from e
    if not vals:
        raise ParseError(f"empty trace reply {text[:60]!r}")
    if expect_header_count:
        n = int(vals[0])
        data = vals[1:]
        if len(data) != n:
            raise ParseError(f"trace announced {n} points but {len(data)} received")
        return data
    return vals


def parse_marker(text: str) -> dict:
    """MKR? / MKR1? / MKR2? -> {'x': wavelength_nm_or_THz, 'y': level}. Empty reply = no marker."""
    nums = numbers(text)
    if len(nums) < 2:
        raise ParseError(f"marker reply has <2 numbers: {text!r}")
    return {"x": nums[0], "y": nums[1], "raw": text.strip()}


_LEVEL_UNIT = re.compile(r"^\s*([A-Za-z]{2})\s*([-+0-9.Ee]+)")


def parse_ref_level(text: str) -> tuple[float, str]:
    """REFL? -> (value, unit). LOG mode returns a plain dBm number; linear mode is prefixed
    PW/NW/UW/MW (manual p. 9-7; exact spacing unverified)."""
    m = _LEVEL_UNIT.match(text)
    if m:
        return float(m.group(2)), m.group(1).upper()
    return first_number(text), "dBm"


def parse_status_byte_flags(stb: int) -> dict:
    """Manual Table 9-6 (p. 9-49)."""
    return {
        "rqs": bool(stb & 0x40),
        "buffer_overflow": bool(stb & 0x20),
        "command_error": bool(stb & 0x08),
        "warning": bool(stb & 0x04),
        "done_fd_or_output": bool(stb & 0x02),
        "sweep_done": bool(stb & 0x01),
    }
