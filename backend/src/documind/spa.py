"""Serving the built Angular app from the API process (production and the container image).

Files from the build directory are served as they are; any other path that is not an API path or
a file name gets ``index.html``, so client-side routes such as ``/documents/<id>`` work on reload.
Uploaded documents are stored elsewhere and are never reachable through this route.
"""

import re
from pathlib import Path, PurePosixPath

from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException

from documind.errors import NotFoundError

# Angular adds a content hash to bundle file names (main-35JR6M3P.js), so they never change.
_HASHED_NAME = re.compile(r"-[A-Z0-9]{8}\.[a-z0-9]+$")
_IMMUTABLE = "public, max-age=31536000, immutable"


def register_spa(app: FastAPI, static_dir: Path) -> None:
    root = static_dir.resolve()
    index = root / "index.html"
    if not index.is_file():
        raise RuntimeError(f"DOCUMIND_STATIC_DIR has no index.html: {root}")

    @app.get("/{path:path}", include_in_schema=False)
    def single_page_app(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise NotFoundError("Not Found")
        if path:
            candidate = (root / path).resolve()
            if candidate.is_relative_to(root) and candidate.is_file():
                cache = _IMMUTABLE if _HASHED_NAME.search(candidate.name) else "no-cache"
                return FileResponse(candidate, headers={"Cache-Control": cache})
            if "." in PurePosixPath(path).name:
                # A missing asset is a 404, not the app shell served under a .js or .css name.
                raise HTTPException(404)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
