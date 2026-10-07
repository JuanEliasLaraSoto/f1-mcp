"""Convierte los fallos de OpenF1 en una respuesta legible en vez de una excepción."""

import functools
from collections.abc import Awaitable, Callable

from f1_mcp.openf1 import OpenF1Error


def friendly_errors[**P](func: Callable[P, Awaitable[str]]) -> Callable[P, Awaitable[str]]:
    """Si la tool falla por OpenF1, devuelve el motivo como texto. Así el modelo puede
    explicárselo al usuario o reintentar, en lugar de recibir un traceback.
    functools.wraps conserva nombre, docstring y firma: el esquema MCP no cambia."""

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> str:
        try:
            return await func(*args, **kwargs)
        except OpenF1Error as exc:
            return f"No he podido obtener los datos de OpenF1: {exc}"

    return wrapper
