import { HttpClient, HttpEvent, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  AskResponse,
  ChunkDetail,
  ChunkPage,
  ClientConfig,
  DocumentSummary,
  SearchResponse,
} from './api.models';

/** Thin typed wrapper around the HTTP API. All URLs are same-origin (`/api/...`). */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  config(): Observable<ClientConfig> {
    return this.http.get<ClientConfig>('/api/config');
  }

  health(): Observable<{ status: string }> {
    return this.http.get<{ status: string }>('/api/health');
  }

  listDocuments(): Observable<DocumentSummary[]> {
    return this.http.get<DocumentSummary[]>('/api/documents');
  }

  getDocument(id: string): Observable<DocumentSummary> {
    return this.http.get<DocumentSummary>(`/api/documents/${encodeURIComponent(id)}`);
  }

  /** Emits upload progress events, then the accepted document. */
  uploadDocument(file: File): Observable<HttpEvent<DocumentSummary>> {
    const body = new FormData();
    body.append('file', file, file.name);
    return this.http.post<DocumentSummary>('/api/documents', body, {
      observe: 'events',
      reportProgress: true,
    });
  }

  deleteDocument(id: string): Observable<void> {
    return this.http.delete<void>(`/api/documents/${encodeURIComponent(id)}`);
  }

  getChunks(id: string, offset: number, limit: number): Observable<ChunkPage> {
    const params = new HttpParams().set('offset', offset).set('limit', limit);
    return this.http.get<ChunkPage>(`/api/documents/${encodeURIComponent(id)}/chunks`, { params });
  }

  getChunk(chunkId: number): Observable<ChunkDetail> {
    return this.http.get<ChunkDetail>(`/api/chunks/${chunkId}`);
  }

  fileUrl(id: string): string {
    return `/api/documents/${encodeURIComponent(id)}/file`;
  }

  search(query: string, documentId: string | null, limit = 20): Observable<SearchResponse> {
    let params = new HttpParams().set('q', query).set('limit', limit);
    if (documentId) {
      params = params.set('document_id', documentId);
    }
    return this.http.get<SearchResponse>('/api/search', { params });
  }

  ask(question: string, documentIds: string[] | null): Observable<AskResponse> {
    return this.http.post<AskResponse>('/api/ask', {
      question,
      document_ids: documentIds && documentIds.length ? documentIds : null,
    });
  }
}
