/** Shapes returned by the DocuMind API (see backend/src/documind/schemas.py). */

export type DocumentStatus = 'processing' | 'ready' | 'failed';
export type FileType = 'pdf' | 'txt';

export interface ClientConfig {
  llm_enabled: boolean;
  llm_model: string | null;
  allowed_file_types: FileType[];
  max_upload_bytes: number;
  max_pdf_pages: number;
  max_query_chars: number;
  max_question_chars: number;
}

export interface DocumentSummary {
  id: string;
  name: string;
  file_type: FileType;
  size_bytes: number;
  status: DocumentStatus;
  failure_code: string | null;
  failure_message: string | null;
  page_count: number | null;
  empty_page_count: number | null;
  chunk_count: number;
  char_count: number;
  created_at: string;
  processed_at: string | null;
}

export interface Chunk {
  id: number;
  ordinal: number;
  page: number | null;
  line_start: number | null;
  line_end: number | null;
  text: string;
}

export interface ChunkPage {
  document_id: string;
  total: number;
  offset: number;
  limit: number;
  items: Chunk[];
}

export interface ChunkDetail extends Chunk {
  document_id: string;
  document_name: string;
}

/** A [start, end) character range inside an excerpt. */
export type Span = [number, number];

export interface SearchHit {
  chunk_id: number;
  document_id: string;
  document_name: string;
  file_type: FileType;
  ordinal: number;
  page: number | null;
  line_start: number | null;
  line_end: number | null;
  excerpt: string;
  highlights: Span[];
  excerpt_starts_mid_text: boolean;
  excerpt_ends_mid_text: boolean;
}

export interface SearchResponse {
  query: string;
  searched_for: string[];
  total_passages: number;
  total_documents: number;
  results: SearchHit[];
}

export type AnswerMode = 'generated' | 'retrieval_only' | 'insufficient_evidence';

export interface AskResponse {
  mode: AnswerMode;
  question: string;
  searched_for: string[];
  /** Generated text with [S1]-style citations; only when mode is "generated". */
  answer: string | null;
  /** Ids of cited passages. Passage n (1-based) is "S<n>". */
  cited: string[];
  passages: SearchHit[];
  /** Set when AI answers are on but the provider failed; passages are still returned. */
  generation_error: { code: string; message: string } | null;
  model: string | null;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    request_id: string;
    details?: unknown;
  };
}
