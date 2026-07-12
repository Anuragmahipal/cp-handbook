"""Explicit JSON serialization for the two independently serializable
roots, :class:`~handbook.learning.page.Page` and
:class:`~handbook.learning.path.LearningPath`.

Every model in this package already gets ``model_dump_json`` /
``model_validate_json`` for free from Pydantic -- these functions are
a thin, deliberate layer on top, for two reasons:

1. A single obvious entry point (``dump_page`` / ``load_page``) rather
   than every caller needing to know which Pydantic method to call and
   with which options.
2. A schema-version check *before* Pydantic attempts to parse the
   payload, so data from a future, incompatible version of this
   package fails with a clear :class:`~handbook.learning.exceptions.
   SchemaVersionError` naming the mismatch, instead of an opaque
   validation error (or worse, a payload that happens to parse but
   means something subtly different).
"""

from __future__ import annotations

import json

from handbook.learning.exceptions import SchemaVersionError
from handbook.learning.page import Page
from handbook.learning.path import LearningPath
from handbook.learning.versioning import CURRENT_SCHEMA_VERSION

_JSONData = str | bytes


def _check_schema_version(payload: dict, *, kind: str) -> None:
    version = payload.get("schema_version")
    if not isinstance(version, int):
        raise SchemaVersionError(
            f"{kind} payload is missing a numeric 'schema_version' field"
        )
    if version > CURRENT_SCHEMA_VERSION:
        raise SchemaVersionError(
            f"{kind} payload declares schema_version={version}, which is "
            f"newer than the schema_version={CURRENT_SCHEMA_VERSION} this "
            "version of handbook.learning knows how to read."
        )


def dump_page(page: Page, *, indent: int | None = 2) -> str:
    """Serialize a ``Page`` to a JSON string."""
    return page.model_dump_json(indent=indent)


def load_page(data: _JSONData) -> Page:
    """Deserialize a ``Page`` from a JSON string/bytes.

    Raises:
        SchemaVersionError: if the payload's ``schema_version`` is
            missing or newer than this package supports.
        pydantic.ValidationError: if the payload's ``schema_version``
            is supported but the rest of the data doesn't validate.
    """
    payload = json.loads(data)
    _check_schema_version(payload, kind="Page")
    return Page.model_validate(payload)


def dump_learning_path(path: LearningPath, *, indent: int | None = 2) -> str:
    """Serialize a ``LearningPath`` to a JSON string."""
    return path.model_dump_json(indent=indent)


def load_learning_path(data: _JSONData) -> LearningPath:
    """Deserialize a ``LearningPath`` from a JSON string/bytes.

    Raises the same errors as :func:`load_page`, for the same reasons.
    """
    payload = json.loads(data)
    _check_schema_version(payload, kind="LearningPath")
    return LearningPath.model_validate(payload)
