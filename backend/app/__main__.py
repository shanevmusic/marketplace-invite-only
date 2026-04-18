"""Development server entry point.

Run with:
    python -m app

This starts a hot-reloading Uvicorn server on port 8000.
"""

from __future__ import annotations

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
