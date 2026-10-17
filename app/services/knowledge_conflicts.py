"""Conservative check for the same policy claim with different numeric values.

This detects literal numeric disagreements, not general semantic contradictions.
Only authorized, approved passages in the response language belong here.
"""

import re
from collections.abc import Iterable
from decimal import Decimal

NUMBER = re.compile(r"(?<!\w)[+-]?\d+(?:[.,]\d+)?(?!\w)")


def has_conflicting_numeric_claims(passages: Iterable[str]) -> bool:
    seen: dict[str, tuple[Decimal, ...]] = {}
    for passage in passages:
        normalized = " ".join(passage.casefold().split())
        numbers = tuple(Decimal(value.replace(",", ".")) for value in NUMBER.findall(normalized))
        if not numbers:
            continue
        claim = NUMBER.sub("#", normalized)
        if claim in seen and seen[claim] != numbers:
            return True
        seen[claim] = numbers
    return False
