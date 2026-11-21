"""Exceptions raised by ando_osa."""


class OsaError(Exception):
    """Base class for all errors."""


class OsaTimeout(OsaError):
    """The instrument did not answer / finish in time."""


class CommandError(OsaError):
    """Bad argument (out of range) or the instrument flagged a command error (status bit 3)."""


class ParseError(OsaError):
    """Instrument reply could not be parsed."""
