export type PageMeta = { total: number; limit: number; offset: number };
export type SourceContext = {
  status?: string; message?: string; source_id?: string; provider_name?: string; rights_status?: string;
  license_name?: string | null; attribution_requirements?: string | null; release_id?: string;
  release_name?: string; file_name?: string; checksum?: string; imported_at?: string;
};
export type PlayerSummary = {
  id: string; canonical_name: string; nationality: string | null; primary_position: string | null;
  identity_status: string; record_count: number; club_count: number; competition_count: number; seasons: string[];
  appearances: number | null; starts: number | null; minutes: number | null; goals: number | null; assists: number | null;
  shots: number | null; shots_on_target: number | null; goals_per90: number | null; assists_per90: number | null;
  contributions_per90: number | null; goals_per_appearance: number | null; assists_per_appearance: number | null;
  goals_per_shot: number | null; shots_per_goal: number | null; shot_accuracy: number | null;
  non_penalty_goals: number | null; non_penalty_goal_contributions: number | null; penalties_scored: number | null; penalties_attempted: number | null;
  non_penalty_contributions_per90: number | null;
  yellow_cards: number | null; red_cards: number | null; second_yellow_cards: number | null; fouls_committed: number | null; fouls_drawn: number | null; own_goals: number | null;
  crosses: number | null; tackles_won: number | null; interceptions: number | null; non_penalty_goals_per90: number | null;
  crosses_per90: number | null; tackles_won_per90: number | null; interceptions_per90: number | null;
  shots_per90: number | null; shots_on_target_per90: number | null;
  goals_against: number | null; goals_against_per90: number | null; shots_on_target_against: number | null;
  saves: number | null; save_percent: number | null; wins: number | null; draws: number | null; losses: number | null;
  clean_sheets: number | null; clean_sheet_percent: number | null; penalties_faced: number | null;
  penalties_against: number | null; penalties_saved: number | null; penalties_missed: number | null;
};
export type PlayerDetail = PlayerSummary & {
  date_of_birth: string | null; birth_year: number | null; preferred_foot: string | null; height_cm: number | null;
  aliases: string[]; source_context: SourceContext;
};
export type StatRecord = {
  id: string; player_id: string; club_id: string | null; club: string | null; competition_id: string | null;
  competition: string | null; season_id: string; season: string; scope: string; position_raw: string | null;
  appearances: number | null; starts: number | null; minutes: number | null; goals: number | null; assists: number | null;
  goal_contributions: number | null; shots: number | null; shots_on_target: number | null; source_sot_percent: number | null;
  non_penalty_goals: number | null; non_penalty_goal_contributions: number | null; penalties_scored: number | null; penalties_attempted: number | null;
  non_penalty_contributions_per90: number | null;
  yellow_cards: number | null; red_cards: number | null; second_yellow_cards: number | null; fouls_committed: number | null; fouls_drawn: number | null; own_goals: number | null;
  crosses: number | null; tackles_won: number | null; interceptions: number | null;
  shot_accuracy: number | null; goals_per90: number | null; assists_per90: number | null; contributions_per90: number | null;
  shots_per90: number | null; shots_on_target_per90: number | null;
  goals_against: number | null; goals_against_per90: number | null; shots_on_target_against: number | null;
  saves: number | null; save_percent: number | null; wins: number | null; draws: number | null; losses: number | null;
  clean_sheets: number | null; clean_sheet_percent: number | null; penalties_faced: number | null;
  penalties_against: number | null; penalties_saved: number | null; penalties_missed: number | null;
  source_id: string; source_name: string; source_release: string;
};
export type PlayerPage = { items: PlayerSummary[]; meta: PageMeta; source_context: SourceContext };
export type Coverage = {
  source_context: SourceContext; player_count: number; record_count: number;
  clubs: { id: string; name: string; players: number; records: number }[];
  competitions: { id: string; name: string; players: number; records: number }[];
  seasons: { id: string; label: string; players: number; records: number }[];
  metrics: { metric: string; available_records: number; total_records: number; status: 'available' | 'partial' | 'unavailable' }[];
};
export type NamedPage<T> = { items: T[]; meta: PageMeta };
export type Club = { id: string; canonical_name: string; players: number; records: number; player_record_goals: number | null; player_record_assists: number | null; player_record_minutes: number | null; competitions: string[]; seasons: string[]; methodology: string };
export type Competition = { id: string; canonical_name: string; players: number; clubs: number; records: number; player_record_goals: number | null; player_record_assists: number | null; seasons: string[]; methodology: string };
export type Season = { id: string; label: string; players: number; clubs: number; competitions: number; records: number };
export type CompetitionEdition = { id: string; label: string; players: number; clubs: number; records: number };
export type MetricDefinition = { metric_key: string; display_name: string; description: string; data_type: string; unit: string; formula: string | null; required_fields_json: string; availability_status: string; minimum_data_requirements: string | null };
export type DataLabMetrics = { items: MetricDefinition[]; available_metrics: string[]; unsupported: string[] };
export type V2Query = {
  search?: string; club_id?: string; competition_id?: string; season_id?: string; position?: string;
  minimum_minutes?: number; sort_by?: string; order?: 'asc' | 'desc'; limit?: number; offset?: number;
};
export type ComparePayload = { player_ids: string[]; season_id?: string; competition_id?: string; minimum_minutes?: number };
export type ComparisonResult = {
  items: (PlayerSummary & { records: StatRecord[] })[];
  scope: Record<string, unknown>;
  methodology: string;
  source_context: SourceContext;
};
export type LabPayload = { visualization: 'table' | 'histogram' | 'scatter' | 'correlation'; metrics: string[]; method?: 'pearson' | 'spearman'; season_id?: string; competition_id?: string; club_id?: string; position?: string; minimum_minutes?: number; limit?: number };
export type VisualizationKind = 'bar' | 'histogram' | 'scatter' | 'line' | 'boxplot' | 'correlation_heatmap';
export type AnalyticsScope = { season_id?: string; competition_id?: string; club_id?: string; position?: string; minimum_minutes?: number };
export type DescriptivePayload = AnalyticsScope & { metrics: string[]; group_by?: 'position' | 'competition' | 'club' | 'season' };
export type VisualizationPayload = DescriptivePayload & { visualization: VisualizationKind; method?: 'pearson' | 'spearman' };
export type OutlierPayload = AnalyticsScope & { metric: string; multiplier?: number; limit?: number };
export type MetricSummary = { metric: string; count: number; mean: number | null; median: number | null; standard_deviation: number | null; variance: number | null; minimum: number | null; q1: number | null; q2: number | null; q3: number | null; interquartile_range: number | null; maximum: number | null };
export type DescriptiveResult = { metrics: string[]; record_count: number; summary: MetricSummary[]; groups: { group: string; record_count: number; player_count: number; metrics: MetricSummary[] }[]; group_by: string | null; methodology: string };
export type OutlierResult = { metric: string; n: number; q1: number | null; q3: number | null; iqr: number | null; multiplier?: number; lower_bound: number | null; upper_bound: number | null; outlier_count: number; items: { record_id: string; player_id: string; player: string; position_raw: string | null; club: string | null; competition: string | null; season: string; [metric: string]: string | number | null }[]; methodology?: string };
export type AnalyticsQuality = { total_records: number; total_columns: number; missing_cells: number; completeness_percent: number | null; duplicate_source_key_records: number; duplicate_content_records: number; potential_invalid_values: Record<string, number>; numeric_columns: string[]; categorical_columns: string[]; columns: { column: string; declared_type: string; dtype: string; missing_count: number; missing_percent: number | null; unique_values: number }[]; methodology: string };
export type HistogramBin = { from: number; to: number; count: number };
export type ScatterPoint = { player_id: string; player: string; club: string | null; competition: string | null; x: number; y: number };
export type LabTableRow = { player_id: string; player: string; club: string | null; competition: string | null; season: string; values: Record<string, number> };
type LabShared = { metrics: string[]; summary?: MetricSummary[]; units?: string[]; source_context?: SourceContext; n?: number };
export type LabResult =
  | (LabShared & { visualization: 'histogram'; n: number; items: HistogramBin[] })
  | (LabShared & { visualization: 'scatter'; total: number; items: ScatterPoint[] })
  | (LabShared & { visualization: 'table'; total: number; items: LabTableRow[] })
  | (LabShared & { visualization: 'correlation'; n: number; value: number | null; unit: string; note: string; interpretation: string; items?: never[] });
export type Leaderboard = { metric: string; unit: string; minimum_minutes: number; eligible_count: number; percentile_method: string; items: (PlayerSummary & { percentile: number; cohort_size: number })[]; methodology: string };
export type PositionAnalysis = { listed_position: string; players: number; records: number; goals: number | null; assists: number | null; average_minutes: number | null };
export type CompetitionAnalysis = { competition_id: string; competition: string; season_id: string; season: string; players: number; clubs: number; records: number; goals: number | null; assists: number | null; shots: number | null; shots_on_target: number | null; average_minutes: number | null; goals_per_player: number | null; assists_per_player: number | null };
export type IdentitySummary = { source_local_keys: number; verified_external_ids: number; decision_statuses: Record<string, number>; ambiguous_name_groups: number; ambiguity_examples: { normalized_name: string; candidate_count: number; candidates: { id: string; canonical_name: string; birth_year: number | null; nationality: string | null; identity_status: string }[] }[]; note: string };

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
const TIMEOUT_MS = 12_000;
let requestQueue: Promise<void> = Promise.resolve();
function enqueueRequest<T>(signal: AbortSignal, run: () => Promise<T>): Promise<T> {
  const previous = requestQueue;
  let release!: () => void;
  requestQueue = new Promise<void>(resolve => { release = resolve; });
  return previous.then(async () => {
    try {
      if (signal.aborted) throw signal.reason ?? new DOMException('The request was cancelled.', 'AbortError');
      return await run();
    } finally {
      release();
    }
  });
}
const query = (values: Record<string, string | number | undefined>) => {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => { if (value !== undefined && value !== '') params.set(key, String(value)); });
  const result = params.toString(); return result ? `?${result}` : '';
};

async function request<T>(path: string, options: { signal?: AbortSignal; method?: 'GET' | 'POST'; body?: unknown } = {}): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(new DOMException('Timed out', 'TimeoutError')), TIMEOUT_MS);
  const onAbort = () => controller.abort(options.signal?.reason);
  options.signal?.addEventListener('abort', onAbort, { once: true });
  try {
    const response = await enqueueRequest(controller.signal, () => fetch(`${API_BASE}/api/v2${path}`, {
      method: options.method ?? 'GET', signal: controller.signal,
      headers: { Accept: 'application/json', ...(options.body ? { 'Content-Type': 'application/json' } : {}) },
      ...(options.body ? { body: JSON.stringify(options.body) } : {}),
    }));
    if (!response.ok) {
      let message = `PITCHIQ API request failed (${response.status}).`;
      try {
        const payload: unknown = await response.json();
        if (payload && typeof payload === 'object') {
          const envelope = payload as { error?: { message?: string }; detail?: string };
          message = envelope.error?.message ?? envelope.detail ?? message;
        }
      } catch { /* The response may not be JSON. */ }
      throw new Error(message);
    }
    return await response.json() as T;
  } catch (error) {
    if (options.signal?.aborted) throw options.signal.reason ?? error;
    if (controller.signal.aborted) throw new Error('The request timed out. Please retry.');
    if (error instanceof TypeError) throw new Error('Could not connect to the PITCHIQ v2 API. Check that the backend is running.');
    throw error;
  } finally {
    window.clearTimeout(timer); options.signal?.removeEventListener('abort', onAbort);
  }
}

async function requestBlob(path: string, body: unknown, signal?: AbortSignal, accept = 'text/csv', method: 'GET' | 'POST' = 'POST'): Promise<Blob> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(new DOMException('Timed out', 'TimeoutError')), TIMEOUT_MS);
  const onAbort = () => controller.abort(signal?.reason);
  signal?.addEventListener('abort', onAbort, { once: true });
  try {
    const response = await enqueueRequest(controller.signal, () => fetch(`${API_BASE}/api/v2${path}`, { method, signal: controller.signal, headers: { Accept: accept, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) }));
    if (!response.ok) {
      let message = `PITCHIQ API request failed (${response.status}).`;
      try { const payload: unknown = await response.json(); if (payload && typeof payload === 'object') { const envelope = payload as { error?: { message?: string }; detail?: string }; message = envelope.error?.message ?? envelope.detail ?? message; } } catch { /* The response may not be JSON. */ }
      throw new Error(message);
    }
    return await response.blob();
  } catch (error) {
    if (signal?.aborted) throw signal.reason ?? error;
    if (controller.signal.aborted) throw new Error('The request timed out. Please retry.');
    if (error instanceof TypeError) throw new Error('Could not connect to the PITCHIQ v2 API. Check that the backend is running.');
    throw error;
  } finally { window.clearTimeout(timer); signal?.removeEventListener('abort', onAbort); }
}

export const v2Api = {
  coverage: (signal?: AbortSignal) => request<Coverage>('/coverage', { signal }),
  identitySummary: (signal?: AbortSignal) => request<IdentitySummary>('/identity/summary', { signal }),
  identityReview: (status = 'needs_review', signal?: AbortSignal) => request<{ id: string; source_player_key: string; canonical_name: string | null; status: string; evidence: Record<string, unknown> }[]>(`/identity/review${query({ status })}`, { signal }),
  sources: (signal?: AbortSignal) => request<{ items: Record<string, unknown>[]; note: string }>('/sources', { signal }),
  players: (filters: V2Query, signal?: AbortSignal) => request<PlayerPage>(`/players${query(filters as Record<string, string | number | undefined>)}`, { signal }),
  player: (id: string, signal?: AbortSignal) => request<PlayerDetail>(`/players/${encodeURIComponent(id)}`, { signal }),
  playerSeasons: (id: string, signal?: AbortSignal) => request<{ items: StatRecord[]; meta: PageMeta; source_context: SourceContext }>(`/players/${encodeURIComponent(id)}/seasons?limit=200`, { signal }),
  playerCareer: (id: string, signal?: AbortSignal) => request<{ items: Record<string, unknown>[]; source_context: SourceContext }>(`/players/${encodeURIComponent(id)}/career`, { signal }),
  clubs: (filters: { search?: string; competition_id?: string; season_id?: string; limit?: number; offset?: number } = {}, signal?: AbortSignal) => request<NamedPage<Club>>(`/clubs${query(filters)}`, { signal }),
  club: (id: string, signal?: AbortSignal) => request<Club & { country: string | null; competitions: string[]; seasons: string[]; source_context: SourceContext }>(`/clubs/${encodeURIComponent(id)}`, { signal }),
  clubPlayers: (id: string, filters: { season_id?: string; competition_id?: string; limit?: number; offset?: number }, signal?: AbortSignal) => request<PlayerPage>(`/clubs/${encodeURIComponent(id)}/players${query(filters)}`, { signal }),
  competitions: (filters: { search?: string; season_id?: string; limit?: number; offset?: number } = {}, signal?: AbortSignal) => request<NamedPage<Competition>>(`/competitions${query(filters)}`, { signal }),
  competition: (id: string, signal?: AbortSignal) => request<Omit<Competition, 'seasons'> & { seasons: CompetitionEdition[]; source_context: SourceContext }>(`/competitions/${encodeURIComponent(id)}`, { signal }),
  competitionPlayers: (id: string, filters: { season_id?: string; position?: string; minimum_minutes?: number; limit?: number; offset?: number }, signal?: AbortSignal) => request<PlayerPage>(`/competitions/${encodeURIComponent(id)}/players${query(filters)}`, { signal }),
  seasons: (signal?: AbortSignal) => request<{ items: Season[]; source_context: SourceContext }>('/seasons', { signal }),
  season: (id: string, signal?: AbortSignal) => request<Season & { source_context: SourceContext }>(`/seasons/${encodeURIComponent(id)}`, { signal }),
  compare: (payload: ComparePayload, signal?: AbortSignal) => request<ComparisonResult>('/compare/players', { method: 'POST', body: payload, signal }),
  leaderboard: (filters: { metric?: string; season_id?: string; competition_id?: string; position?: string; minimum_minutes?: number; limit?: number } = {}, signal?: AbortSignal) => request<Leaderboard>(`/leaderboards${query(filters)}`, { signal }),
  positions: (filters: { season_id?: string; competition_id?: string } = {}, signal?: AbortSignal) => request<{ items: PositionAnalysis[]; methodology: string }>(`/analytics/positions${query(filters)}`, { signal }),
  competitionAnalysis: (season_id?: string, signal?: AbortSignal) => request<{ items: CompetitionAnalysis[]; methodology: string }>(`/analytics/competitions${query({ season_id })}`, { signal }),
  metrics: (signal?: AbortSignal) => request<DataLabMetrics>('/data-lab/metrics', { signal }),
  dataLab: (payload: LabPayload, signal?: AbortSignal) => request<LabResult>('/data-lab/query', { method: 'POST', body: payload, signal }),
  descriptive: (payload: DescriptivePayload, signal?: AbortSignal) => request<DescriptiveResult>('/analytics/descriptive', { method: 'POST', body: payload, signal }),
  outliers: (filters: OutlierPayload, signal?: AbortSignal) => request<OutlierResult>(`/analytics/outliers${query(filters)}`, { signal }),
  quality: (signal?: AbortSignal) => request<AnalyticsQuality>('/analytics/quality', { signal }),
  qualityVisualization: (signal?: AbortSignal) => requestBlob('/analytics/quality/visualization', undefined, signal, 'image/png', 'GET'),
  visualization: (payload: VisualizationPayload, signal?: AbortSignal) => requestBlob('/analytics/visualizations', payload, signal, 'image/png'),
  exportDescriptive: (payload: DescriptivePayload, signal?: AbortSignal) => requestBlob('/exports/analytics-summary', payload, signal),
  exportOutliers: (payload: OutlierPayload, signal?: AbortSignal) => requestBlob('/exports/outliers', payload, signal),
  exportPlayers: (filters: V2Query) => `${API_BASE}/api/v2/exports/players${query(filters as Record<string, string | number | undefined>)}`,
  exportLeaderboard: (filters: { metric: string; season_id?: string; competition_id?: string; minimum_minutes?: number; limit?: number }) => `${API_BASE}/api/v2/exports/leaderboards${query(filters)}`,
  exportComparison: (payload: ComparePayload, signal?: AbortSignal) => requestBlob('/exports/comparison', payload, signal),
  exportDataLab: (payload: LabPayload, signal?: AbortSignal) => requestBlob('/exports/data-lab', payload, signal),
};
