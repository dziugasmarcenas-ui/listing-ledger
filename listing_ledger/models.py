import re
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

_ID = re.compile(r"^[A-Za-z0-9_-]+$")
MAX_PRICE_MINOR = 1_000_000_000_000


def utc_iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=80)
    listing_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    observed_at: datetime
    status: Literal["active", "unavailable", "unknown"]
    price_minor: Annotated[StrictInt, Field(ge=0, le=MAX_PRICE_MINOR)] | None
    currency: Literal["EUR", "USD", "JPY"]
    supersedes: str | None = None

    @field_validator("event_id", "listing_id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        if not _ID.fullmatch(value):
            raise ValueError("must contain only letters, digits, underscore, or hyphen")
        return value

    @field_validator("supersedes")
    @classmethod
    def valid_supersedes(cls, value: str | None) -> str | None:
        if value is not None and not _ID.fullmatch(value):
            raise ValueError("must contain only letters, digits, underscore, or hyphen")
        return value

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be empty")
        return value

    @field_validator("observed_at", mode="before")
    @classmethod
    def parse_iso_timestamp(cls, value: object) -> datetime:
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str):
            raise ValueError("observed_at must be an ISO-8601 timezone-aware timestamp string")  # noqa: TRY004 - Pydantic maps ValueError to HTTP 422
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                "observed_at must be an ISO-8601 timezone-aware timestamp string"
            ) from exc
        return parsed

    @field_validator("observed_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value.astimezone(UTC)


class EventRecord(Event):
    sequence: int
    received_at: str


class Projection(BaseModel):
    listing_id: str
    title: str | None
    status: Literal["active", "unavailable", "unknown"]
    price_minor: int | None
    currency: str | None
    last_known_price_minor: int | None
    last_known_price_currency: str | None
    source_event_id: str | None
    applied_event_ids: list[str]
    as_of_sequence: int
    has_observations: bool
