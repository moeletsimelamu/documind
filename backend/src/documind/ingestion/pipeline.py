"""Upload intake and background document processing.

Intake (in the request): validate, store under a generated name, record as ``processing``.
Processing (after the response): extract in an isolated process, chunk, then write all chunks and
the ``ready`` status in one transaction, or record a failure the user can read.
"""

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from typing import BinaryIO

import anyio
import anyio.to_thread
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from documind.config import Settings
from documind.db import session_scope
from documind.errors import AppError
from documind.ingestion.chunking import chunk_lines
from documind.ingestion.extraction import (
    ExtractedDocument,
    ExtractionError,
    ExtractionRequest,
    extract_file,
)
from documind.ingestion.isolation import IsolationCrashError, IsolationTimeoutError, run_isolated
from documind.ingestion.validation import (
    PDF_SIGNATURE_WINDOW,
    TextDecodingError,
    UnsupportedFileError,
    check_content,
    decode_text,
    file_type_from_name,
    sanitize_display_name,
)
from documind.models import Chunk, Document, DocumentStatus, utc_now
from documind.storage import LocalFileStorage

logger = logging.getLogger(__name__)

COPY_BLOCK_BYTES = 64 * 1024


class FileTooLargeError(AppError):
    status_code = HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    code = "file_too_large"


class EmptyFileError(AppError):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    code = "empty_file"


class DuplicateDocumentError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "duplicate_document"

    def __init__(self, existing: Document) -> None:
        super().__init__(
            f"This file is already in your library as “{existing.display_name}”.",
            details={"document_id": existing.id, "status": existing.status.value},
        )


def too_large_message(settings: Settings) -> str:
    return f"The file is larger than the {settings.max_upload_mb} MB limit."


def _find_by_hash(session: Session, sha256: str) -> Document | None:
    return session.scalar(select(Document).where(Document.sha256 == sha256))


def accept_upload(
    *,
    session: Session,
    storage: LocalFileStorage,
    settings: Settings,
    filename: str | None,
    source: BinaryIO,
) -> Document:
    """Validate and store an upload, and record it as ``processing``."""
    display_name = sanitize_display_name(filename)
    file_type = file_type_from_name(display_name)

    temp_path, handle = storage.create_temp()
    try:
        digest = hashlib.sha256()
        size = 0
        head = b""
        with handle:
            while block := source.read(COPY_BLOCK_BYTES):
                size += len(block)
                if size > settings.max_upload_bytes:
                    raise FileTooLargeError(too_large_message(settings))
                if len(head) < PDF_SIGNATURE_WINDOW:
                    head += block[: PDF_SIGNATURE_WINDOW - len(head)]
                digest.update(block)
                handle.write(block)
        if size == 0:
            raise EmptyFileError("The file is empty.")
        check_content(file_type, head)
        if file_type == "txt":
            try:
                decode_text(temp_path.read_bytes())
            except TextDecodingError as exc:
                raise UnsupportedFileError(str(exc)) from exc

        sha256 = digest.hexdigest()
        if (existing := _find_by_hash(session, sha256)) is not None:
            raise DuplicateDocumentError(existing)

        document_id = str(uuid.uuid4())
        document = Document(
            id=document_id,
            display_name=display_name,
            stored_name=f"{document_id}.{file_type}",
            file_type=file_type,
            size_bytes=size,
            sha256=sha256,
            status=DocumentStatus.PROCESSING,
        )
        storage.commit(temp_path, document.stored_name)
        session.add(document)
        try:
            session.commit()
        except IntegrityError:
            # Two identical files uploaded at the same moment: the other one won.
            session.rollback()
            storage.delete(document.stored_name)
            if (existing := _find_by_hash(session, sha256)) is not None:
                raise DuplicateDocumentError(existing) from None
            raise
        logger.info("Accepted document %s (%s, %d bytes)", document_id, file_type, size)
        return document
    finally:
        storage.discard_temp(temp_path)


@dataclass(frozen=True)
class ChunkDraft:
    text: str
    page: int | None
    line_start: int | None
    line_end: int | None


def build_chunks(document: ExtractedDocument) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    for page in document.pages:
        if page.number is not None:
            # PDF: chunk each page separately so every chunk has exactly one page number.
            drafts.extend(
                ChunkDraft(text=c.text, page=page.number, line_start=None, line_end=None)
                for c in chunk_lines(page.text, joiner=" ")
            )
        else:
            drafts.extend(
                ChunkDraft(text=c.text, page=None, line_start=c.first_line, line_end=c.last_line)
                for c in chunk_lines(page.text, joiner="\n")
            )
    return drafts


class DocumentProcessor:
    """Processes uploaded documents in the background, a limited number at a time."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        storage: LocalFileStorage,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage
        self._settings = settings
        self._limiter: anyio.CapacityLimiter | None = None

    async def process_in_background(self, document_id: str) -> None:
        """Wait for a processing slot without holding a worker thread, then process.

        Queued documents wait on this limiter in the event loop. Waiting inside a worker thread
        instead would let a burst of uploads occupy the server's shared thread pool, which every
        API request also needs (measured: health checks took up to 26 s during 120 uploads).
        """
        if self._limiter is None:
            self._limiter = anyio.CapacityLimiter(self._settings.max_concurrent_processing)
        await anyio.to_thread.run_sync(self.process, document_id, limiter=self._limiter)

    def process(self, document_id: str) -> None:
        try:
            self._process(document_id)
        except Exception:
            logger.exception("Unexpected error while processing document %s", document_id)
            self._mark_failed(
                document_id,
                "processing_error",
                "The document could not be processed because of an unexpected error.",
            )

    def _process(self, document_id: str) -> None:
        started = time.perf_counter()
        with self._session_factory() as session:
            document = session.get(Document, document_id)
            if document is None or document.status != DocumentStatus.PROCESSING:
                return
            stored_name, file_type = document.stored_name, document.file_type

        request = ExtractionRequest(
            path=str(self._storage.path_for(stored_name)),
            file_type=file_type,
            max_pages=self._settings.max_pdf_pages,
            max_chars=self._settings.max_extracted_chars,
        )
        timeout = self._settings.extraction_timeout_seconds
        try:
            extracted = run_isolated(
                extract_file,
                request,
                timeout,
                memory_limit_bytes=self._settings.extraction_memory_limit_mb * 1024 * 1024,
            )
        except ExtractionError as exc:
            self._mark_failed(document_id, exc.code, exc.message)
            return
        except IsolationTimeoutError:
            self._mark_failed(
                document_id,
                "timeout",
                f"Reading this file took longer than {timeout:g} seconds and was stopped. "
                "The file may be damaged or unusually complex.",
            )
            return
        except MemoryError:
            self._mark_failed(
                document_id,
                "too_large",
                "Reading this file needed more memory than the "
                f"{self._settings.extraction_memory_limit_mb} MB limit allows.",
            )
            return
        except IsolationCrashError:
            self._mark_failed(
                document_id, "processing_error", "The document could not be processed."
            )
            return

        drafts = build_chunks(extracted)
        if self._store(document_id, extracted, drafts):
            logger.info(
                "Processed document %s: %s pages, %d chunks in %.1f s",
                document_id,
                extracted.page_count if extracted.page_count is not None else "-",
                len(drafts),
                time.perf_counter() - started,
            )

    def _store(
        self, document_id: str, extracted: ExtractedDocument, drafts: list[ChunkDraft]
    ) -> bool:
        """Write all chunks and mark the document ready, atomically. False if it was deleted."""
        with self._session_factory() as session:
            document = session.get(Document, document_id)
            if document is None:
                logger.info("Document %s was deleted during processing", document_id)
                return False
            session.add_all(
                Chunk(
                    document_id=document_id,
                    ordinal=ordinal,
                    page=draft.page,
                    line_start=draft.line_start,
                    line_end=draft.line_end,
                    text=draft.text,
                )
                for ordinal, draft in enumerate(drafts)
            )
            document.status = DocumentStatus.READY
            document.page_count = extracted.page_count
            document.empty_page_count = extracted.empty_page_count
            document.chunk_count = len(drafts)
            document.char_count = extracted.char_count
            document.failure_code = None
            document.failure_message = None
            document.processed_at = utc_now()
            try:
                session.commit()
            except (IntegrityError, StaleDataError):
                session.rollback()
                if session.get(Document, document_id) is not None:
                    raise
                logger.info("Document %s was deleted during processing", document_id)
                return False
        return True

    def _mark_failed(self, document_id: str, code: str, message: str) -> None:
        with self._session_factory() as session:
            document = session.get(Document, document_id)
            if document is None:
                return
            document.status = DocumentStatus.FAILED
            document.failure_code = code
            document.failure_message = message
            document.processed_at = utc_now()
            try:
                session.commit()
            except StaleDataError:
                session.rollback()
                return
        logger.info("Document %s failed: %s", document_id, code)

    def recover_after_restart(self) -> None:
        """Fail documents left mid-processing by a shutdown, and remove orphaned files."""
        with session_scope(self._session_factory) as session:
            interrupted = session.scalars(
                select(Document).where(Document.status == DocumentStatus.PROCESSING)
            ).all()
            for document in interrupted:
                document.status = DocumentStatus.FAILED
                document.failure_code = "interrupted"
                document.failure_message = (
                    "Processing was interrupted because the server stopped. Delete this "
                    "document and upload the file again."
                )
                document.processed_at = utc_now()
            referenced = set(session.scalars(select(Document.stored_name)))
        removed = self._storage.remove_unreferenced(referenced)
        if interrupted or removed:
            logger.info(
                "Start-up recovery: %d interrupted documents marked failed, %d orphaned files "
                "removed",
                len(interrupted),
                removed,
            )
