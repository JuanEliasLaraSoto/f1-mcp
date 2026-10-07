"""Turns OpenF1 failures into a readable answer instead of an exception."""

import functools
from collections.abc import Awaitable, Callable

from f1_mcp.openf1 import OpenF1Error


def friendly_errors[**P](func: Callable[P, Awaitable[str]]) -> Callable[P, Awaitable[str]]:
    """If the tool fails because of OpenF1, return the reason as text, so the model
    can explain it to the user or retry instead of receiving a traceback.
    functools.wraps keeps name, docstring and signature: the MCP schema is unchanged."""

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> str:
        try:
            return await func(*args, **kwargs)
        except OpenF1Error as exc:
            return f"Could not get data from OpenF1: {exc}"

    return wrapper
