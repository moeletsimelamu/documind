"""Upload validation: file names, file types and content checks.

The extension decides which parser is used, and the content must agree with it. Nothing here
trusts the browser-supplied content type.
"""

import codecs
import unicodedata
from http import HTTPStatus
from pathlib import PurePosixPath

from documind.config import ALLOWED_FILE_TYPES
from documind.errors import AppError

MAX_DISPLAY_NAME_CHARS = 200
PDF_SIGNATURE = b"%PDF-"
# The PDF specification allows bytes before the header; readers accept it within the first 1 KiB.
PDF_SIGNATURE_WINDOW = 1024


class UnsupportedFileError(AppError):
    status_code = HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    code = "unsupported_file_type"


class TextDecodingError(Exception):
    pass


def sanitize_display_name(raw: str | None) -> str:
    """A safe name for display. Strips directories, control and formatting characters."""
    name = (raw or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = unicodedata.normalize("NFC", name)
    # Category C covers control characters and invisible formatting characters such as the
    # right-to-left override, which can disguise an extension ("report‮fdp.exe").
    name = "".join(ch for ch in name if not unicodedata.category(ch).startswith("C"))
    name = " ".join(name.split())
    if len(name) > MAX_DISPLAY_NAME_CHARS:
        suffix = PurePosixPath(name).suffix
        if len(suffix) > 10:
            suffix = ""
        name = name[: MAX_DISPLAY_NAME_CHARS - len(suffix)].rstrip() + suffix
    return name or "untitled"


def file_type_from_name(display_name: str) -> str:
    suffix = PurePosixPath(display_name).suffix.lower().lstrip(".")
    if suffix not in ALLOWED_FILE_TYPES:
        allowed = " and ".join(t.upper() for t in ALLOWED_FILE_TYPES)
        shown = f"“.{suffix}” files" if suffix else "Files without an extension"
        raise UnsupportedFileError(f"{shown} are not supported. Upload {allowed} files.")
    return suffix


def check_content(file_type: str, head: bytes) -> None:
    """Check the first bytes of the file agree with its extension."""
    if file_type == "pdf" and PDF_SIGNATURE not in head[:PDF_SIGNATURE_WINDOW]:
        raise UnsupportedFileError("This file has a .pdf extension but is not a PDF.")


def decode_text(data: bytes) -> str:
    """Decode a text file: UTF-8 (with or without BOM) or UTF-16 with a BOM.

    Raises TextDecodingError for anything else, including binary files renamed to .txt.
    """
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError as exc:
            raise TextDecodingError("The file is not valid UTF-16 text.") from exc
    if b"\x00" in data:
        raise TextDecodingError("This file has a .txt extension but contains binary data.")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise TextDecodingError(
            "The text file is not UTF-8 encoded. Save it as UTF-8 and upload it again."
        ) from exc
