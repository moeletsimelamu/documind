import { HttpErrorResponse } from '@angular/common/http';

import { NETWORK_ERROR_CODE, isUnreachable, toApiError } from './api-error';

const envelope = (code: string, message: string) => ({
  error: { code, message, request_id: 'abc123' },
});

describe('toApiError', () => {
  it('uses the code and message from the API error envelope', () => {
    const error = new HttpErrorResponse({
      status: 409,
      error: {
        error: {
          ...envelope('duplicate_document', 'Already there.').error,
          details: { document_id: 'd1' },
        },
      },
    });

    expect(toApiError(error)).toEqual({
      status: 409,
      code: 'duplicate_document',
      message: 'Already there.',
      details: { document_id: 'd1' },
    });
  });

  it('treats no response at all as the server being unreachable', () => {
    const error = new HttpErrorResponse({ status: 0 });

    expect(isUnreachable(error)).toBe(true);
    expect(toApiError(error).code).toBe(NETWORK_ERROR_CODE);
  });

  it('treats a 5xx without the envelope as a proxy that could not reach the API', () => {
    const error = new HttpErrorResponse({ status: 500, error: 'Error occurred while proxying' });

    expect(isUnreachable(error)).toBe(true);
    expect(toApiError(error).message).toContain("Can't reach the DocuMind server");
  });

  it('keeps a real server error from the API as a server error', () => {
    const error = new HttpErrorResponse({
      status: 500,
      error: envelope('internal_error', 'Something went wrong on the server.'),
    });

    expect(isUnreachable(error)).toBe(false);
    expect(toApiError(error)).toMatchObject({ status: 500, code: 'internal_error' });
  });

  it('handles other unexpected responses and non-HTTP errors', () => {
    expect(toApiError(new HttpErrorResponse({ status: 418, error: 'teapot' })).code).toBe(
      'unexpected',
    );
    expect(toApiError(new Error('boom')).code).toBe('unexpected');
  });
});
