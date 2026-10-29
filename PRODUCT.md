# Product

Listing Ledger is a local, fictional-data demo of reliable marketplace observation processing. It makes the difference between when an observation was received and when it says the listing was observed visible, while preserving retries and corrections as append-only history.

The primary visitor is a reviewer exploring a synthetic listing’s event history. They can replay ingestion attempts, inspect the backend’s reconstructed listing projection at each sequence, and copy a source event as JSON. The product demonstrates storage and reconstruction behavior; it does not source listings, infer sales, or make purchase decisions.

The interface runs locally through the same-origin FastAPI app. It is a single-user demo, not a hosted multi-user service.
