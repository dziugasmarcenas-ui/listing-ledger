from .models import Event


def demo_events():
    def e(event_id, time, status="active", price=8000, supersedes=None):
        return Event(
            event_id=event_id,
            listing_id="demo-jacket",
            title="Canvas work jacket",
            observed_at=f"2026-10-{time}Z",
            status=status,
            price_minor=price,
            currency="EUR",
            supersedes=supersedes,
        )

    return [
        ("Initial observation", e("demo-1", "20T09:00:00")),
        ("Lower asking price", e("demo-2", "20T12:00:00", price=6500)),
        ("Late observation", e("demo-3", "20T10:00:00", price=7500)),
        ("Exact retry", e("demo-2", "20T12:00:00", price=6500)),
        ("Unavailable", e("demo-4", "21T09:00:00", "unavailable", None)),
        ("Correction", e("demo-5", "20T12:00:00", price=6000, supersedes="demo-2")),
    ]
