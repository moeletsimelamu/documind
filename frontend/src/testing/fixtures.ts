import { AskResponse, ClientConfig, DocumentSummary, SearchHit } from '../app/core/api.models';

export function makeDocument(overrides: Partial<DocumentSummary> = {}): DocumentSummary {
  return {
    id: 'doc-1',
    name: 'report.pdf',
    file_type: 'pdf',
    size_bytes: 2048,
    status: 'ready',
    failure_code: null,
    failure_message: null,
    page_count: 3,
    empty_page_count: 0,
    chunk_count: 4,
    char_count: 3000,
    created_at: '2026-10-20T09:00:00Z',
    processed_at: '2026-10-20T09:00:05Z',
    ...overrides,
  };
}

export function makeHit(overrides: Partial<SearchHit> = {}): SearchHit {
  return {
    chunk_id: 11,
    document_id: 'doc-1',
    document_name: 'report.pdf',
    file_type: 'pdf',
    ordinal: 2,
    page: 2,
    line_start: null,
    line_end: null,
    excerpt: 'Supplier delays slowed deliveries.',
    highlights: [[0, 8]],
    excerpt_starts_mid_text: false,
    excerpt_ends_mid_text: false,
    ...overrides,
  };
}

export function makeConfig(overrides: Partial<ClientConfig> = {}): ClientConfig {
  return {
    llm_enabled: false,
    llm_model: null,
    allowed_file_types: ['pdf', 'txt'],
    max_upload_bytes: 20 * 1024 * 1024,
    max_pdf_pages: 500,
    max_query_chars: 300,
    max_question_chars: 1000,
    ...overrides,
  };
}

export function makeAskResponse(overrides: Partial<AskResponse> = {}): AskResponse {
  return {
    mode: 'retrieval_only',
    question: 'Which supplier was late?',
    searched_for: ['supplier', 'late'],
    answer: null,
    cited: [],
    passages: [makeHit()],
    generation_error: null,
    model: null,
    ...overrides,
  };
}

/** Let pending microtasks and change detection settle. */
export async function settle(fixture: { whenStable(): Promise<unknown> }): Promise<void> {
  await fixture.whenStable();
}
