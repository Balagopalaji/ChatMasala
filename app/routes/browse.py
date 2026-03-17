"""Directory browse endpoint for workspace path selection."""
import os
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter()

HOME = Path.home()


@router.get("/api/browse")
def browse_directory(path: str = Query(default=None)):
    """Return directory listing for the given path, defaulting to home."""
    try:
        target = Path(path).expanduser().resolve() if path else HOME
        if not target.exists() or not target.is_dir():
            target = HOME

        entries = []
        try:
            for item in sorted(target.iterdir()):
                if item.is_dir() and not item.name.startswith("."):
                    entries.append({
                        "name": item.name,
                        "path": str(item),
                        "is_dir": True,
                    })
        except PermissionError:
            pass

        return JSONResponse({
            "current": str(target),
            "parent": str(target.parent) if target != target.parent else None,
            "entries": entries,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
