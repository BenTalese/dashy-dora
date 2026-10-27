import importlib
import inspect
import logging
import os
import pkgutil
import re
from pathlib import Path
from typing import Any, List

from pydantic import BaseModel

def apply_exclusion_filter(collection: List[str], exclusion_patterns: List[str]) -> None:
    '''
    Summary
    -------
    Applies RegEx exclusion patterns to a collection of strings and removes any
    items that match those patterns.

    Parameters
    ----------
    `collection` A list of strings that represents the collection of items that need
    to be filtered.\n
    `exclusion_patterns` A list of regular expression patterns that should be used to exclude
    certain items from the collection.

    Example
    -------
    my_collection = ["a", "b", "c", "d"]\n
    exclusion_patterns = ["b", "d"]\n
    MyClass.apply_exclusion_filter(my_collection, exclusion_patterns)\n
    print(my_collection)  # Output: ["a", "c"]

    '''
    for _ExclusionPattern in exclusion_patterns:
        collection[:] = [_Item for _Item in collection if not re.match(_ExclusionPattern, _Item)]


def _to_package_name(path_to_search: Path | str) -> str:
    """Accept either a package dotted name ("dora_api.features") or a
    path-like value (legacy callers pass `Path() / 'dora_api' /
    'features'`). Returns the dotted package name either way."""
    s = str(path_to_search).strip()
    s = s.replace("\\", "/").strip("/")
    return s.replace("/", ".")


def _raise_import_failure(name: str) -> None:
    """`pkgutil.walk_packages` swallows an ImportError from a sub-*package*
    when no `onerror` is given, so a feature package that fails to import
    silently drops every route under it and the app boots with a hole in its
    API (FU-719). Log it with the traceback and re-raise: a feature that
    can't import fails the boot loudly."""
    logging.getLogger(__name__).exception("Feature package %s failed to import", name)
    raise


def _iter_submodules(package_name: str):
    """pkgutil-based recursive walk of a package. Works in both
    source-tree and PyInstaller-frozen contexts (the on-disk
    `os.walk` approach the previous implementation used silently
    returned nothing in a frozen bundle because the source tree
    wasn't on disk)."""
    pkg = importlib.import_module(package_name)
    if not hasattr(pkg, "__path__"):
        return
    for info in pkgutil.walk_packages(pkg.__path__, prefix=f"{package_name}.", onerror=_raise_import_failure):
        # Skip the package's own __init__ modules — they're already
        # imported as part of `import_module(package_name)`. Modules
        # with a name ending in `.__init__` don't show up via
        # walk_packages anyway, so the only thing to skip explicitly
        # is sub-packages we'll recurse into (info.ispkg=True).
        if info.ispkg:
            continue
        yield importlib.import_module(info.name)


def get_classes_ending_with(term: str, path_to_search: Path | str):
    _Classes: list = []
    for _Module in _iter_submodules(_to_package_name(path_to_search)):
        for _, _Class in inspect.getmembers(_Module, inspect.isclass):
            if (_Class.__name__.lower().endswith(term.lower())
                    and _Class.__module__ == _Module.__name__):
                _Classes.append(_Class)
    return _Classes


def get_attributes_ending_with(term: str, path_to_search: Path | str):
    _Attributes: list = []
    for _Module in _iter_submodules(_to_package_name(path_to_search)):
        for _AttributeName, _AttributeValue in inspect.getmembers(_Module):
            if (_AttributeName.lower().endswith(term.lower())
                    and _AttributeValue not in _Attributes):
                _Attributes.append(_AttributeValue)
    return _Attributes


def field_of(model: type[BaseModel], field: str) -> str:
    if field not in model.model_fields:
        raise ValueError(f"'{field}' is not a field on '{model.__name__}'")
    return field


def pluralize(count: int, singular: str, plural: str | None = None) -> str:
    '''
    Return the correct noun form for `count`: `singular` when |count| == 1,
    otherwise `plural` (defaulting to `singular` + "s").

    DR-4 (FU-578 #10) — single source for noun pluralisation so user-facing
    copy never ships the lazy "day(s)" placeholder. Call sites keep control of
    the number and surrounding words: f"{n} {pluralize(n, 'day')} ago".
    '''
    return singular if abs(count) == 1 else (plural or f"{singular}s")


def get_request_body() -> Any:
    '''
    Retrieves the request body from the current Flask request context.

    Returns:
        The deserialized request body, or None if no request body is present.
    '''
    from flask import request
    return getattr(request, 'request_body', None)


