from __future__ import annotations

import time
from typing import Callable, Optional, Tuple, Type, TypeVar

T = TypeVar("T")


def with_retries(fn: Callable[[], T], attempts: int = 3, backoff: float = 1.0,
                 retry_on: Tuple[Type[BaseException], ...] = (Exception,),
                 on_retry: Optional[Callable[[int, BaseException], None]] = None) -> T:
    """Run fn, retrying only on `retry_on` exceptions with exponential backoff."""
    last: Optional[BaseException] = None
    for i in range(1, attempts + 1):
        try:
            return fn()
        except retry_on as exc:  # type: ignore[misc]
            last = exc
            if i == attempts:
                break
            if on_retry:
                on_retry(i, exc)
            time.sleep(backoff * (2 ** (i - 1)))
    assert last is not None
    raise last
