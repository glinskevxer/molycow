"""Hot lab record keeping for a nuclear pharmacy.

The package is layered. ``units`` and ``decay`` know physics and nothing else,
``model`` holds the records the pharmacy keeps, ``store`` puts them in sqlite,
the service packages apply the rules a technologist works to, and ``cli`` is
the only place that prints.
"""

__version__ = "0.2.0"

__all__ = ["__version__"]
