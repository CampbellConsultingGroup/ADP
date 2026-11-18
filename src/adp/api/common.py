"""Small pieces every router needs, written once (ADP-blp.27).

* ``session_dependency`` -- the FastAPI dependency that opens a database session from a
  store module. It was a four-line function repeated in every router (thirty times).
* ``named_path_param`` -- lets one generic handler serve several routes whose path
  parameter is named differently in each (``capability_id``, ``agent_id``, ...), so
  routes generated from a table publish exactly the paths hand-written ones did.
"""

from __future__ import annotations

import importlib
import inspect
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, get_type_hints

from sqlalchemy.ext.asyncio import AsyncSession


def session_dependency(store_module: str) -> Callable[[], AsyncIterator[AsyncSession]]:
    """A dependency yielding a session from ``<store_module>._get_session_factory()``.

    The module is named, not passed, and imported on first use: several routers reach
    into another domain's store only for one reverse lookup, and importing it at module
    load would create import cycles. The factory is looked up on every request, so a
    test that swaps a store's ``_session_factory`` is honoured.

    Each call returns a new function, so two routers' dependencies stay distinct keys for
    ``app.dependency_overrides``.
    """

    async def get_session() -> AsyncIterator[AsyncSession]:
        factory = importlib.import_module(store_module)._get_session_factory()
        async with factory() as session:
            yield session

    get_session.__qualname__ = f"session_dependency({store_module!r})"
    return get_session


def named_path_param(
    handler: Callable[..., Awaitable[Any]], generic: str, name: str
) -> Callable[..., Any]:
    """``handler`` takes a path parameter called ``generic``; return it taking ``name``.

    FastAPI reads the path parameter's name from the endpoint's signature, so the wrapper
    publishes the renamed signature and passes the value back under the generic name.
    """
    # Resolve the annotations here: with `from __future__ import annotations` they are strings,
    # and FastAPI would look them up in this module's globals instead of the handler's.
    hints = get_type_hints(handler, include_extras=True)
    signature = inspect.signature(handler)
    renamed = [
        p.replace(
            name=name if p.name == generic else p.name,
            annotation=hints.get(p.name, p.annotation),
        )
        for p in signature.parameters.values()
    ]

    async def endpoint(**kwargs: Any) -> Any:
        kwargs[generic] = kwargs.pop(name)
        return await handler(**kwargs)

    endpoint.__signature__ = signature.replace(  # type: ignore[attr-defined]
        parameters=renamed, return_annotation=hints.get("return", signature.return_annotation)
    )
    endpoint.__doc__ = handler.__doc__
    return endpoint
