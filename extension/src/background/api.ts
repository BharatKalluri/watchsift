import ky from 'ky';
import { ApiError } from './engine';

declare const __API_ORIGIN__: string;

const api = ky.create({
  cache: 'no-store',
  credentials: 'omit',
  redirect: 'error',
  referrerPolicy: 'no-referrer',
  // Engine persists retry backoff; callers supply their timeout/cancellation signal.
  retry: 0,
  timeout: false,
  maxResponseSize: 100000,
  hooks: {
    afterResponse: [
      ({ response }) => {
        if (response.ok) return;
        const retry = response.headers.get('Retry-After');
        const seconds =
          retry && /^\d+$/.test(retry)
            ? Number(retry)
            : retry
              ? (Date.parse(retry) - Date.now()) / 1000
              : 30;
        throw new ApiError(Number.isFinite(seconds) ? seconds : 30);
      },
    ],
  },
});

export function request(path: string, payload: unknown, signal: AbortSignal): Promise<unknown> {
  return api.post(`${__API_ORIGIN__}${path}`, { json: payload, signal }).json();
}
