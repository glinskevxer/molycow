"""The records the pharmacy keeps, as plain frozen objects.

Nothing in here touches sqlite, prints, or asks what time it is. A record
validates itself on the way in and answers questions about itself, which is
what makes the rules above it readable.
"""

from molycow.model.register import AuthorizedUser, Customer, CustomerKind

__all__ = ["AuthorizedUser", "Customer", "CustomerKind"]
