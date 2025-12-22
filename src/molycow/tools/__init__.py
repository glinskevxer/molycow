"""The checks this repository holds itself to.

Each one is a module with a ``main`` that prints what it found and exits
non zero if it found anything. They run as their own steps in ci and again
from the test suite, so a check that stops working is a failing test rather
than a green build that stopped looking.
"""
