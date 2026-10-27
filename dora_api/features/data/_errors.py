"""Typed failure outcomes for the data feature's handlers.

The restore, inspect and spreadsheet handlers used to return a bare `str`
and the routes dispatched on `startswith("No staged upload")` /
`startswith("… rolled back")`, one of them parsing the upload id back *out
of the message* — the same shape 13-R1's 500 came from (finalisation 18-R11,
R-010). A handler now returns its result or a `DataError`; `respond_to`
turns the error into the one problem document its kind deserves.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from flask import Response

from dora_api.infrastructure.api_response import bad_request, internal_server_error, not_found

ErrorKind = Literal["invalid", "upload_missing", "rolled_back"]


@dataclass(frozen=True, slots=True)
class DataError:
    detail: str
    kind: ErrorKind = "invalid"
    upload_id: str | None = None


def invalid(detail: str) -> DataError:
    """A request the handler refuses (400)."""
    return DataError(detail=detail)


def upload_missing(upload_id: str) -> DataError:
    """The staged upload the request names is gone (404)."""
    return DataError(
        detail=f"No staged upload found for id {upload_id}.",
        kind="upload_missing", upload_id=upload_id,
    )


def rolled_back(what: str, exc: BaseException) -> DataError:
    """The write failed part-way and the transaction was rolled back (500)."""
    return DataError(detail=f"{what} failed and was rolled back: {exc}", kind="rolled_back")


def respond_to(error: DataError) -> Response:
    if error.kind == "upload_missing":
        return not_found("Upload", error.upload_id)
    if error.kind == "rolled_back":
        return internal_server_error(error.detail)
    return bad_request(error.detail)
