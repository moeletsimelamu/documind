import { HttpErrorResponse } from '@angular/common/http';

import { ApiErrorBody } from './api.models';

/** An API failure reduced to what the interface needs: a code and a message safe to show. */
export interface ApiError {
  status: number;
  code: string;
  message: string;
  details?: unknown;
}

export const NETWORK_ERROR_CODE = 'network';

function isErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== 'object' || value === null || !('error' in value)) {
    return false;
  }
  const error = (value as { error: unknown }).error;
  return typeof error === 'object' && error !== null && 'message' in error && 'code' in error;
}

/**
 * True when the request never reached the DocuMind API. The API answers every request, even an
 * unexpected failure, with its JSON error envelope, so a 5xx without one came from something in
 * between (a proxy that could not connect), and status 0 means no response at all.
 */
export function isUnreachable(error: HttpErrorResponse): boolean {
  return error.status === 0 || (error.status >= 500 && !isErrorBody(error.error));
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof HttpErrorResponse) {
    if (isUnreachable(error)) {
      return {
        status: error.status,
        code: NETWORK_ERROR_CODE,
        message: "Can't reach the DocuMind server. Check that it is running.",
      };
    }
    if (isErrorBody(error.error)) {
      return {
        status: error.status,
        code: error.error.error.code,
        message: error.error.error.message,
        details: error.error.error.details,
      };
    }
    return {
      status: error.status,
      code: 'unexpected',
      message: `The server returned an unexpected response (${error.status}).`,
    };
  }
  return { status: -1, code: 'unexpected', message: 'Something went wrong. Please try again.' };
}
