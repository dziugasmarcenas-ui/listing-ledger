import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .models import Event, EventRecord, Projection, utc_iso


class LedgerStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS streams (
                    stream_id TEXT PRIMARY KEY, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    stream_id TEXT NOT NULL REFERENCES streams(stream_id),
                    event_id TEXT NOT NULL, listing_id TEXT NOT NULL,
                    payload TEXT NOT NULL, sequence INTEGER NOT NULL,
                    received_at TEXT NOT NULL,
                    PRIMARY KEY(stream_id, event_id),
                    UNIQUE(stream_id, sequence)
                );
                CREATE INDEX IF NOT EXISTS event_listing_sequence
                    ON events(stream_id, listing_id, sequence);
            """)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=20, isolation_level=None)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA busy_timeout=20000")
            yield db
        except BaseException:
            db.rollback()
            raise
        else:
            db.commit()
        finally:
            db.close()

    @staticmethod
    def _record(row) -> EventRecord:
        return EventRecord.model_validate(
            {
                **json.loads(row["payload"]),
                "sequence": row["sequence"],
                "received_at": row["received_at"],
            }
        )

    def create_stream(self) -> str:
        stream_id = str(uuid.uuid4())
        with self._connect() as db:
            db.execute("INSERT INTO streams VALUES (?, ?)", (stream_id, utc_iso(datetime.now(UTC))))
        return stream_id

    def has_stream(self, stream_id: str) -> bool:
        with self._connect() as db:
            return (
                db.execute("SELECT 1 FROM streams WHERE stream_id=?", (stream_id,)).fetchone()
                is not None
            )

    def add_event(self, stream_id: str, event: Event) -> tuple[EventRecord, bool]:
        payload = event.model_dump(mode="json")
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM streams WHERE stream_id=?", (stream_id,)).fetchone():
                raise KeyError("unknown stream")
            prior = db.execute(
                "SELECT * FROM events WHERE stream_id=? AND event_id=?", (stream_id, event.event_id)
            ).fetchone()
            if prior:
                if prior["payload"] != canonical:
                    raise ValueError("event_conflict")
                return self._record(prior), True
            if event.supersedes is not None:
                target = db.execute(
                    "SELECT * FROM events WHERE stream_id=? AND event_id=?",
                    (stream_id, event.supersedes),
                ).fetchone()
                if target is None:
                    raise ValueError("supersedes must reference an earlier event in this stream")
                original = Event.model_validate(json.loads(target["payload"]))
                if original.supersedes is not None:
                    raise ValueError("correction chains are not allowed")
                if original.listing_id != event.listing_id:
                    raise ValueError("correction target must belong to the same listing")
                if original.observed_at != event.observed_at:
                    raise ValueError("correction must retain the original observed_at")
            sequence = db.execute(
                "SELECT COALESCE(MAX(sequence),0)+1 FROM events WHERE stream_id=?", (stream_id,)
            ).fetchone()[0]
            received_at = utc_iso(datetime.now(UTC))
            db.execute(
                "INSERT INTO events VALUES (?,?,?,?,?,?)",
                (stream_id, event.event_id, event.listing_id, canonical, sequence, received_at),
            )
            row = db.execute(
                "SELECT * FROM events WHERE stream_id=? AND event_id=?", (stream_id, event.event_id)
            ).fetchone()
            return self._record(row), False

    def events(self, stream_id: str) -> list[EventRecord]:
        with self._connect() as db:
            return [
                self._record(row)
                for row in db.execute(
                    "SELECT * FROM events WHERE stream_id=? ORDER BY sequence", (stream_id,)
                )
            ]

    def projection(
        self, stream_id: str, listing_id: str, through_sequence: int | None = None
    ) -> Projection:
        with self._connect() as db:
            if not db.execute("SELECT 1 FROM streams WHERE stream_id=?", (stream_id,)).fetchone():
                raise KeyError("unknown stream")
            latest_sequence = db.execute(
                "SELECT COALESCE(MAX(sequence),0) FROM events WHERE stream_id=?", (stream_id,)
            ).fetchone()[0]
            as_of_sequence = (
                min(through_sequence, latest_sequence)
                if through_sequence is not None
                else latest_sequence
            )
            if not db.execute(
                "SELECT 1 FROM events WHERE stream_id=? AND listing_id=?", (stream_id, listing_id)
            ).fetchone():
                raise LookupError("unknown listing")
            if through_sequence is not None and through_sequence < 0:
                raise ValueError("through_sequence must be >= 0")
            sql = "SELECT * FROM events WHERE stream_id=? AND listing_id=?"
            args: list = [stream_id, listing_id]
            if through_sequence is not None:
                sql += " AND sequence<=?"
                args.append(through_sequence)
            received = [self._record(r) for r in db.execute(sql + " ORDER BY sequence", args)]
        corrections: dict[str, EventRecord] = {}
        originals: dict[str, EventRecord] = {}
        for item in received:
            if item.supersedes is None:
                originals[item.event_id] = item
            else:
                corrections[item.supersedes] = item
        effective = [corrections.get(key, original) for key, original in originals.items()]
        effective.sort(key=lambda e: (e.observed_at, e.sequence))
        if not effective:
            return Projection(
                listing_id=listing_id,
                title=None,
                status="unknown",
                price_minor=None,
                currency=None,
                last_known_price_minor=None,
                last_known_price_currency=None,
                source_event_id=None,
                applied_event_ids=[],
                as_of_sequence=as_of_sequence,
                has_observations=False,
            )
        current = effective[-1]
        priced = [e for e in effective if e.price_minor is not None]
        last_price = priced[-1] if priced else None
        return Projection(
            listing_id=listing_id,
            title=current.title,
            status=current.status,
            price_minor=current.price_minor,
            currency=current.currency,
            last_known_price_minor=last_price.price_minor if last_price else None,
            last_known_price_currency=last_price.currency if last_price else None,
            source_event_id=current.event_id,
            applied_event_ids=[e.event_id for e in effective],
            as_of_sequence=as_of_sequence,
            has_observations=True,
        )
