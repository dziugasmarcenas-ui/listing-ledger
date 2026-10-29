import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .demo import demo_events
from .models import Event
from .store import LedgerStore


def create_app(db_path: str | Path) -> FastAPI:
    store = LedgerStore(db_path)
    app = FastAPI(title="Listing Ledger")
    app.state.store = store

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/streams", status_code=201)
    def create_stream():
        return {"stream_id": store.create_stream()}

    @app.post("/api/streams/{stream_id}/events")
    def add_event(stream_id: str, event: Event, response: Response):
        try:
            record, duplicate = store.add_event(stream_id, event)
            response.status_code = 200 if duplicate else 201
            return {"event": record, "duplicate": duplicate}
        except KeyError:
            raise HTTPException(404, "unknown stream")
        except ValueError as exc:
            if str(exc) == "event_conflict":
                raise HTTPException(
                    409,
                    {
                        "code": "event_conflict",
                        "message": "event_id was already used with a different payload",
                    },
                )
            raise HTTPException(422, str(exc))

    @app.get("/api/streams/{stream_id}/events")
    def get_events(stream_id: str):
        if not store.has_stream(stream_id):
            raise HTTPException(404, "unknown stream")
        return {"events": store.events(stream_id)}

    @app.get("/api/streams/{stream_id}/listings/{listing_id}")
    def get_projection(
        stream_id: str, listing_id: str, through_sequence: int | None = Query(None, ge=0)
    ):
        try:
            return store.projection(stream_id, listing_id, through_sequence)
        except KeyError:
            raise HTTPException(404, "unknown stream")
        except LookupError:
            raise HTTPException(404, "unknown listing")
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    @app.post("/api/demo", status_code=201)
    def create_demo():
        stream_id = store.create_stream()
        attempts = []
        for label, event in demo_events():
            record, duplicate = store.add_event(stream_id, event)
            attempts.append(
                {
                    "label": label,
                    "event": event,
                    "duplicate": duplicate,
                    "sequence": record.sequence,
                }
            )
        return {
            "stream_id": stream_id,
            "listing_id": "demo-jacket",
            "attempts": attempts,
            "events": store.events(stream_id),
        }

    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

        @app.get("/")
        def root():
            return FileResponse(static_dir / "index.html")

    return app


app = create_app(os.getenv("LISTING_LEDGER_DB", "./var/ledger.sqlite3"))
