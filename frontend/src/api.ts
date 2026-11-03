import type { CompetitionAnalysis, Correlation, Filters, Leaderboard, Overview, Player, PlayerOption, PlayerPage, PositionSummary, Quality, Team } from './types';

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
const TIMEOUT_MS = 12_000;

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(new DOMException('Request timed out', 'TimeoutError')), TIMEOUT_MS);
  const forwardAbort = () => controller.abort(signal?.reason);
  signal?.addEventListener('abort', forwardAbort, { once: true });
  try {
    const response = await fetch(`${API_BASE}${path}`, { signal: controller.signal, headers: { Accept: 'application/json' } });
    if (!response.ok) {
      let detail = `Request failed (${response.status})`;
      try { const body = await response.json() as { detail?: string }; if (body.detail) detail = body.detail; } catch { /* response may not be JSON */ }
      throw new Error(detail);
    }
    return await response.json() as T;
  } catch (error) {
    if (signal?.aborted) throw signal.reason ?? error;
    if (controller.signal.aborted) throw new Error('The request timed out. Check that the API is running and try again.');
    if (error instanceof TypeError) throw new Error('Could not connect to the PITCHIQ API. Check that the backend is running.');
    throw error;
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener('abort', forwardAbort);
  }
}

export type PlayerQuery = { search?: string; min_minutes?: number; position?: string; squad?: string; competition?: string; sort_by?: string; order?: 'asc' | 'desc'; limit?: number; offset?: number };
export type OverviewFilters = Pick<PlayerQuery, 'min_minutes' | 'position' | 'squad' | 'competition'>;
const queryString = (query: Record<string, string | number | undefined>) => {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => { if (value !== undefined && value !== '') params.set(key, String(value)); });
  return params.toString();
};

export const api = {
  health: (signal?: AbortSignal) => request<{ status: string; rows: number; columns: number }>('/api/health', signal),
  overview: (signal?: AbortSignal, filters: OverviewFilters = {}) => request<Overview>(`/api/overview?${queryString(filters as Record<string, string | number | undefined>)}`, signal),
  players: (query: PlayerQuery = {}, signal?: AbortSignal) => request<PlayerPage>(`/api/players?${queryString(query as Record<string, string | number | undefined>)}`, signal),
  player: (rank: number, signal?: AbortSignal) => request<Player>(`/api/players/${rank}`, signal),
  teams: (signal?: AbortSignal, filters: OverviewFilters = {}) => request<Team[]>(`/api/teams?${queryString(filters as Record<string, string | number | undefined>)}`, signal),
  filters: (signal?: AbortSignal) => request<Filters>('/api/filters', signal),
  playerOptions: (signal?: AbortSignal) => request<PlayerOption[]>('/api/player-options', signal),
  positions: (signal?: AbortSignal) => request<PositionSummary[]>('/api/analysis/positions', signal),
  correlation: (signal?: AbortSignal) => request<Correlation>('/api/analysis/correlation', signal),
  quality: (signal?: AbortSignal) => request<Quality>('/api/quality', signal),
  compare: (ids: number[], signal?: AbortSignal) => request<Player[]>(`/api/compare?ids=${ids.join(',')}`, signal),
  leaderboard: (metric: string, minMinutes: number, competition?: string, signal?: AbortSignal) => request<Leaderboard>(`/api/leaderboards?${queryString({ metric, min_minutes: minMinutes, competition })}`, signal),
  competitions: (competition?: string, signal?: AbortSignal) => request<CompetitionAnalysis>(`/api/analysis/competitions?${queryString({ competition })}`, signal),
};
