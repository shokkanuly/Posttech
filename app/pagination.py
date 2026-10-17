"""Shared bounds for collection endpoints; arrays stay compatible with the UI."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query


@dataclass(frozen=True)
class Pagination:
    limit: int
    offset: int


def pagination(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1000000),
) -> Pagination:
    return Pagination(limit, offset)


Page = Annotated[Pagination, Depends(pagination)]
