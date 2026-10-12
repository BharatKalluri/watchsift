import pLimit from 'p-limit';
import { Card, DEFAULTS, Resolution, SettingsSchema, validResponse } from '../shared/types';

interface State {
  status: string;
  retryAt: number;
}
interface Storage {
  get(keys: string[]): Promise<Record<string, unknown>>;
  set(values: Record<string, unknown>): Promise<void>;
}
type Transport = (path: string, data: unknown, signal: AbortSignal) => Promise<unknown>;

const initial: State = { status: 'Open Netflix or Prime Video to start', retryAt: 0 };

export class Engine {
  readonly run = pLimit(1);
  constructor(
    private storage: Storage,
    private transport: Transport,
    private now = Date.now,
  ) {}

  async preferences() {
    const data = await this.storage.get(['settings']);
    const parsed = SettingsSchema.safeParse({ ...DEFAULTS, ...(data.settings || {}) });
    return parsed.success ? parsed.data : { ...DEFAULTS };
  }

  private async load(): Promise<State> {
    const { engine } = await this.storage.get(['engine']);
    const state = engine as Partial<State> | undefined;
    return {
      status: state?.status?.startsWith('Connected · IMDb data ')
        ? 'Connected'
        : (state?.status ?? initial.status),
      retryAt: state?.retryAt ?? 0,
    };
  }

  async initialize() {
    // Drop obsolete telemetry and cache data while preserving preferences and retry backoff.
    await this.storage.set({ engine: await this.load(), settings: await this.preferences() });
  }

  async status() {
    const state = await this.load();
    return { status: (await this.preferences()).enabled ? state.status : 'WatchSift is paused' };
  }

  async resolve(cards: Card[]): Promise<{ results: Resolution[]; status: string }> {
    const state = await this.load();
    if (!(await this.preferences()).enabled) return { results: [], status: 'WatchSift is paused' };
    const results: Resolution[] = [];
    if (cards.length && this.now() >= state.retryAt) {
      try {
        const response = await this.transport('/v1/resolve', { cards }, AbortSignal.timeout(5000));
        if (!validResponse(response, cards)) throw new Error('Invalid rating response');
        results.push(...response.results);
        state.status = 'Connected';
      } catch (error) {
        const retrySeconds = error instanceof ApiError ? error.retrySeconds : 30;
        state.retryAt = this.now() + Math.min(3600, Math.max(1, retrySeconds)) * 1000;
        state.status = 'Ratings unavailable · retrying shortly';
      }
    }
    await this.storage.set({ engine: state });
    return { results, status: state.status };
  }
}

export class ApiError extends Error {
  constructor(public retrySeconds: number) {
    super('API unavailable');
  }
}
