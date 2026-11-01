export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };

const configuredBase = (import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '')).trim().replace(/\/+$/, '');
export const API_BASE_URL = configuredBase;
export const API_PREFIX = '/api/v1';

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(message: string, status: number, detail?: unknown) {
    super(message); this.name = 'ApiError'; this.status = status; this.detail = detail;
  }
}

export async function apiRequest<T = Json>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers, credentials: 'include' });
  const type = response.headers.get('content-type') ?? '';
  const payload: unknown = type.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof payload === 'object' && payload !== null && 'detail' in payload ? (payload as {detail: unknown}).detail : payload;
    throw new ApiError(typeof detail === 'string' ? detail : `Request failed (HTTP ${response.status})`, response.status, detail);
  }
  return payload as T;
}

export const getHealth = () => apiRequest<{status:string;service:string;version:string}>(`${API_PREFIX}/health`);
export const getReadiness = () => apiRequest<{status:string;service:string;scope:string}>(`${API_PREFIX}/ready`);
export const getOpenApi = () => apiRequest<Record<string, any>>('/openapi.json');
export const searchLiterature = (query: string, limit = 10) => apiRequest(`${API_PREFIX}/literature/search`, { method:'POST', body:JSON.stringify({query, limit, providers:['openalex','crossref'], persist_results:false}) });
export const getVocabulary = () => apiRequest(`${API_PREFIX}/knowledge/vocabulary`);
export const searchConcepts = (query: string) => apiRequest(`${API_PREFIX}/knowledge/concepts?${new URLSearchParams({query,limit:'25'})}`);
export const createConcept = (payload: unknown) => apiRequest(`${API_PREFIX}/knowledge/concepts`, {method:'POST',body:JSON.stringify(payload)});
export const runMath = (path: string, payload: unknown) => apiRequest(`${API_PREFIX}/math${path}`, {method:'POST',body:JSON.stringify(payload)});
