"""Semantic aliases for project-related path values."""

from typing import Annotated

from pydantic import Field

EncodedProjectKey = Annotated[
    str,
    Field(description="Opaque encoded project key used in URLs and persisted records."),
]
AbsoluteProjectPath = Annotated[
    str,
    Field(description="Absolute filesystem path to a project checkout."),
]
ProjectDisplayPath = Annotated[
    str,
    Field(description="Human-readable project label or display path."),
]

__all__ = [
    "AbsoluteProjectPath",
    "EncodedProjectKey",
    "ProjectDisplayPath",
]
