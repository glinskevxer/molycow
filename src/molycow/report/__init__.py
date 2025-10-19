"""Reports, which assemble rows and hand them back rather than printing them.

A report knows nothing about a terminal. It builds sections of plain lines and
the cli decides what to do with them, which is what lets the same report be
tested without capturing output.
"""

from molycow.report.sheet import Section, Sheet

__all__ = ["Section", "Sheet"]
