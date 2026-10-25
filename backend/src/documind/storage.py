"""Storage for uploaded files.

Files are stored under server-generated names (``<uuid>.<ext>``) in one directory that is not
served by the web server. User-supplied file names never reach a path.
"""

import logging
import re
import tempfile
from pathlib import Path
from typing import IO

logger = logging.getLogger(__name__)

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_STORED_NAME = re.compile(rf"^{_UUID}\.(pdf|txt)$")
TEMP_PREFIX = ".upload-"


class LocalFileStorage:
    """Local-disk storage. The single place that turns stored names into paths."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def create_temp(self) -> tuple[Path, IO[bytes]]:
        """A new temporary file inside the storage root (so the final move is a rename)."""
        handle = tempfile.NamedTemporaryFile(  # noqa: SIM115 - the caller owns and closes it
            dir=self.root, prefix=TEMP_PREFIX, delete=False
        )
        return Path(handle.name), handle

    def commit(self, temp_path: Path, stored_name: str) -> None:
        temp_path.replace(self.path_for(stored_name))

    def discard_temp(self, temp_path: Path) -> None:
        if temp_path.parent.resolve() != self.root.resolve() or not temp_path.name.startswith(
            TEMP_PREFIX
        ):
            raise ValueError("Not a temporary upload file.")
        temp_path.unlink(missing_ok=True)

    def path_for(self, stored_name: str) -> Path:
        if not _STORED_NAME.fullmatch(stored_name):
            raise ValueError("Invalid stored file name.")
        path = (self.root / stored_name).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("Stored file path escapes the storage directory.")
        return path

    def read_bytes(self, stored_name: str) -> bytes:
        return self.path_for(stored_name).read_bytes()

    def delete(self, stored_name: str) -> bool:
        """Delete a stored file. Returns False (and logs) if it could not be removed."""
        try:
            self.path_for(stored_name).unlink(missing_ok=True)
        except OSError:
            # e.g. Windows refuses to delete a file another process has open. The orphan is
            # removed by the start-up sweep.
            logger.warning("Could not delete %s; it will be removed on restart", stored_name)
            return False
        return True

    def stored_names(self) -> set[str]:
        return {p.name for p in self.root.iterdir() if p.is_file()}

    def remove_unreferenced(self, referenced: set[str]) -> int:
        """Delete files no document refers to, including abandoned temporary uploads."""
        removed = 0
        for name in self.stored_names() - referenced:
            if not (_STORED_NAME.fullmatch(name) or name.startswith(TEMP_PREFIX)):
                continue  # never touch files DocuMind did not create
            try:
                (self.root / name).unlink(missing_ok=True)
                removed += 1
            except OSError:
                logger.warning("Could not remove unreferenced file %s", name)
        return removed
