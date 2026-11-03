import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Activity, ArrowLeft, ArrowRight, Download, Search, ShieldCheck } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts';
import { v2Api, type AnalyticsQuality, type Club, type Competition, type Coverage, type DescriptiveResult, type IdentitySummary, type LabPayload, type LabResult, type Leaderboard, type MetricDefinition, type OutlierResult, type PlayerDetail, type PlayerPage, type PlayerSummary, type Season, type StatRecord, type VisualizationKind, type VisualizationPayload } from './v2Api';
import { ActiveFilters, type ActiveFilter } from './components/ActiveFilters';
import { ComparisonExperience } from './components/ComparisonExperience';

const number = (value: number | null | undefined, digits = 0) => value == null || !Number.isFinite(value) ? '—' : new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }).format(value);
function saveBlob(blob: Blob, filename: string) { const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = filename; anchor.style.display = 'none'; document.body.append(anchor); anchor.click(); anchor.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); }
const metricLabel: Record<string, string> = { goals: 'Goals', assists: 'Assists', appearances: 'Appearances', starts: 'Starts', minutes: 'Minutes', shots: 'Shots', shots_on_target: 'Shots on target', shots_per90: 'Shots / 90', shots_on_target_per90: 'Shots on target / 90', goals_per90: 'Goals / 90', assists_per90: 'Assists / 90', contributions_per90: 'Goal contributions / 90', non_penalty_goals_per90: 'Non-penalty goals / 90', non_penalty_contributions_per90: 'Non-penalty contributions / 90', crosses_per90: 'Crosses / 90', tackles_won_per90: 'Tackles won / 90', interceptions_per90: 'Interceptions / 90', goals_per_appearance: 'Goals / appearance', assists_per_appearance: 'Assists / appearance', goals_per_shot: 'Goal conversion', shots_per_goal: 'Shots / goal', shot_accuracy: 'Shooting accuracy', non_penalty_goals: 'Non-penalty goals', non_penalty_goal_contributions: 'Non-penalty contributions', penalties_scored: 'Penalties scored', penalties_attempted: 'Penalties attempted', yellow_cards: 'Yellow cards', red_cards: 'Red cards', second_yellow_cards: 'Second yellow dismissals', fouls_committed: 'Fouls committed', fouls_drawn: 'Fouls drawn', own_goals: 'Own goals', crosses: 'Crosses', tackles_won: 'Tackles won', interceptions: 'Interceptions', goals_against: 'Goalkeeper goals against', goals_against_per90: 'Goalkeeper goals against / 90', shots_on_target_against: 'Shots on target faced', saves: 'Goalkeeper saves', save_percent: 'Goalkeeper save percentage', wins: 'Goalkeeper wins', draws: 'Goalkeeper draws', losses: 'Goalkeeper losses', clean_sheets: 'Clean sheets', clean_sheet_percent: 'Clean-sheet percentage', penalties_faced: 'Penalties faced', penalties_against: 'Penalty goals against', penalties_saved: 'Penalties saved', penalties_missed: 'Penalties missed' };
const useLoad = <T,>(loader: (signal: AbortSignal) => Promise<T>, initial: T) => {
  const [data, setData] = useState(initial); const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError('');
    loader(controller.signal).then(value => { if (!controller.signal.aborted) setData(value); }).catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Unable to load this data.'); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [loader, revision]);
  return { data, loading, error, retry: () => setRevision(x => x + 1) };
};

function V2Heading({ eyebrow, title, children }: { eyebrow: string; title: string; children?: React.ReactNode }) {
  return <div className="page-heading v2-heading pq-page__head"><p className="pq-eyebrow"><i aria-hidden="true"/>{eyebrow}</p><h1 className="pq-page__title">{title}</h1>{children && <p className="pq-page__lede">{children}</p>}</div>;
}
function Loading({ label = 'Loading available dataset…' }: { label?: string }) { return <div className="v2-state" role="status"><span className="v2-spinner" aria-hidden="true"/>{label}</div>; }
function ErrorState({ message, retry }: { message: string; retry: () => void }) { return <div className="notice v2-error" role="alert"><span>{message}</span><button className="retry-button" onClick={retry}>Retry</button>{message.includes('database') && <small>Initialize the v2 database with the documented CLI command, then reload.</small>}</div>; }
function Empty({ children }: { children: React.ReactNode }) { return <div className="panel v2-empty">{children}</div>; }
function Methodology({ children }: { children: React.ReactNode }) { return <div className="methodology-note"><ShieldCheck size={16}/><span>{children}</span></div>; }
function FilterSelect({ label, value, onChange, options, all = 'All' }: { label: string; value: string; onChange: (value: string) => void; options: { value: string; label: string }[]; all?: string }) {
  return <label className="v2-control"><span>{label}</span><select aria-label={label} value={value} onChange={event => onChange(event.target.value)}><option value="">{all}</option>{options.map(item => <option value={item.value} key={item.value}>{item.label}</option>)}</select></label>;
}
function v2Filters(coverage: Coverage | undefined, positions: string[]) {
  return {
    seasons: (coverage?.seasons ?? []).map(x => ({ value: x.id, label: x.label })),
    competitions: (coverage?.competitions ?? []).map(x => ({ value: x.id, label: x.name })),
    clubs: (coverage?.clubs ?? []).map(x => ({ value: x.id, label: x.name })),
    positions: positions.filter(Boolean).map(x => ({ value: x, label: x })),
  };
}
function useCoverage() { const load = useCallback((signal: AbortSignal) => v2Api.coverage(signal), []); return useLoad<Coverage>(load, { source_context: {}, player_count: 0, record_count: 0, clubs: [], competitions: [], seasons: [], metrics: [] }); }
function usePositionOptions() { const load = useCallback((signal: AbortSignal) => v2Api.positions({}, signal), []); return useLoad(load, { items: [], methodology: '' }); }
function useSeasonOptions() { const load = useCallback((signal: AbortSignal) => v2Api.seasons(signal), []); return useLoad(load, { items: [], source_context: {} }); }

export function DatabasePage() {
  const coverage = useCoverage(); const positions = usePositionOptions();
  const [search, setSearch] = useState(''); const [debouncedSearch, setDebouncedSearch] = useState(''); const [position, setPosition] = useState(''); const [season, setSeason] = useState(''); const [competition, setCompetition] = useState(''); const [club, setClub] = useState(''); const [minimumMinutes, setMinimumMinutes] = useState(0); const [sort, setSort] = useState('name'); const [order, setOrder] = useState<'asc' | 'desc'>('asc'); const [offset, setOffset] = useState(0); const [limit, setLimit] = useState(25);
  useEffect(() => { const timer = window.setTimeout(() => { setDebouncedSearch(search.trim()); setOffset(0); }, 250); return () => window.clearTimeout(timer); }, [search]);
  const searchPending = search.trim() !== debouncedSearch;
  const load = useCallback((signal: AbortSignal) => v2Api.players({ search: debouncedSearch || undefined, position: position || undefined, season_id: season || undefined, competition_id: competition || undefined, club_id: club || undefined, minimum_minutes: minimumMinutes, sort_by: sort, order, limit, offset }, signal), [debouncedSearch, position, season, competition, club, minimumMinutes, sort, order, limit, offset]);
  const state = useLoad<PlayerPage>(load, { items: [], meta: { total: 0, limit, offset }, source_context: {} });
  const filters = v2Filters(coverage.data, positions.data.items.map(x => x.listed_position));
  const clearSearch = () => { setSearch(''); setDebouncedSearch(''); setOffset(0); };
  const clear = () => { clearSearch(); setPosition(''); setSeason(''); setCompetition(''); setClub(''); setMinimumMinutes(0); setSort('name'); setOrder('asc'); };
  const searching = state.loading || searchPending;
  return <><V2Heading eyebrow="CANONICAL PLAYER EXPLORER" title="Explore the database.">Search canonical players and filter their source records by season, competition, club, role, and minutes. Each player retains dataset provenance.</V2Heading>
    <div className="v2-filter-grid">
      <div className="searchbox v2-search"><Search size={17} aria-hidden="true"/><label className="sr-only" htmlFor="v2-player-search">Search player, alias, or club</label><input id="v2-player-search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search player, alias, or club…"/>{search && <button type="button" className="v2-search-clear" aria-label="Clear player search" onClick={clearSearch}>×</button>}</div>
      <FilterSelect label="Position" value={position} onChange={value => { setPosition(value); setOffset(0); }} options={filters.positions}/>
      <FilterSelect label="Season" value={season} onChange={value => { setSeason(value); setOffset(0); }} options={filters.seasons}/>
      <FilterSelect label="Competition" value={competition} onChange={value => { setCompetition(value); setOffset(0); }} options={filters.competitions}/>
      <FilterSelect label="Club" value={club} onChange={value => { setClub(value); setOffset(0); }} options={filters.clubs}/>
      <FilterSelect label="Minimum minutes" value={String(minimumMinutes)} onChange={value => { setMinimumMinutes(Number(value)); setOffset(0); }} options={[0, 450, 900, 1800].map(x => ({ value: String(x), label: x ? `${x}+` : 'Any' }))}/>
      <FilterSelect label="Sort by" value={sort} onChange={value => setSort(value)} options={Object.entries({ name: 'Name', goals: 'Goals', assists: 'Assists', minutes: 'Minutes', appearances: 'Appearances', shots: 'Shots', shots_on_target: 'Shots on target', goals_per90: 'Goals / 90', assists_per90: 'Assists / 90', contributions_per90: 'Contributions / 90', non_penalty_goals_per90: 'Non-penalty goals / 90', non_penalty_contributions_per90: 'Non-penalty contributions / 90', shots_per90: 'Shots / 90', shots_on_target_per90: 'Shots on target / 90', tackles_won_per90: 'Tackles won / 90', interceptions_per90: 'Interceptions / 90', shot_accuracy: 'Shooting accuracy' }).map(([value, label]) => ({ value, label }))}/>
      <button className="btn-outline v2-direction" onClick={() => setOrder(value => value === 'asc' ? 'desc' : 'asc')} aria-label={`Sort ${order === 'asc' ? 'descending' : 'ascending'}`}>Order {order === 'asc' ? '↑' : '↓'}</button>
      <button className="btn-outline v2-clear" onClick={clear}>Clear filters</button>
    </div>
    <ActiveFilters items={[
      ...(search.trim() ? [{ name: 'Search', value: search.trim(), onRemove: clearSearch }] : []),
      ...(position ? [{ name: 'Position', value: position, onRemove: () => { setPosition(''); setOffset(0); } }] : []),
      ...(season ? [{ name: 'Season', value: filters.seasons.find(item => item.value === season)?.label ?? season, onRemove: () => { setSeason(''); setOffset(0); } }] : []),
      ...(competition ? [{ name: 'Competition', value: filters.competitions.find(item => item.value === competition)?.label ?? competition, onRemove: () => { setCompetition(''); setOffset(0); } }] : []),
      ...(club ? [{ name: 'Club', value: filters.clubs.find(item => item.value === club)?.label ?? club, onRemove: () => { setClub(''); setOffset(0); } }] : []),
      ...(minimumMinutes ? [{ name: 'Minutes', value: `${minimumMinutes}+`, onRemove: () => { setMinimumMinutes(0); setOffset(0); } }] : []),
    ]}/>
    <div className="v2-results-line"><span aria-live="polite">{searching ? 'Searching…' : state.error ? 'Results unavailable' : `${number(state.data.meta.total)} canonical players`}</span><label>Rows per page <select aria-label="Rows per page" value={limit} onChange={event => { setLimit(Number(event.target.value)); setOffset(0); }}><option>25</option><option>50</option><option>100</option></select></label><a className="btn-outline export-link" href={v2Api.exportPlayers({ search: debouncedSearch || undefined, position: position || undefined, season_id: season || undefined, competition_id: competition || undefined, club_id: club || undefined, minimum_minutes: minimumMinutes })}><Download size={14}/> Export CSV</a></div>
    {state.error && <ErrorState message={state.error} retry={state.retry}/>}
    <div className="panel table-panel v2-table-panel"><div className="table-scroll"><table><caption className="sr-only">Canonical players matching selected filters</caption><thead><tr><th scope="col">PLAYER</th><th scope="col">POSITION</th><th scope="col">CLUBS</th><th scope="col">RECORDS</th><th scope="col">MINUTES</th><th scope="col">GOALS</th><th scope="col">ASSISTS</th><th scope="col">G+A / 90</th><th scope="col">IDENTITY</th></tr></thead><tbody>{!searching && !state.error && state.data.items.map(player => <tr key={player.id}><td><Link className="player-detail-link" to={`/database/player/${encodeURIComponent(player.id)}`}><b>{player.canonical_name}</b></Link><small>{player.nationality ?? 'Nationality unavailable'}</small></td><td>{player.primary_position ?? '—'}</td><td>{number(player.club_count)}</td><td>{number(player.record_count)}</td><td>{number(player.minutes)}</td><td className="lime strong">{number(player.goals)}</td><td>{number(player.assists)}</td><td>{number(player.contributions_per90, 2)}</td><td><span className="v2-status">{player.identity_status}</span></td></tr>)}</tbody></table></div>{searching ? <Loading label="Loading canonical players"/> : !state.error && (state.data.items.length === 0 ? <Empty>No players match this scope. Clear or widen the filters.</Empty> : <div className="v2-pagination"><button className="btn-outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}><ArrowLeft size={14}/> Previous</button><span>Showing {number(offset + 1)}–{number(Math.min(offset + limit, state.data.meta.total))} of {number(state.data.meta.total)}</span><button className="btn-outline" disabled={offset + limit >= state.data.meta.total} onClick={() => setOffset(offset + limit)}>Next <ArrowRight size={14}/></button></div>)}</div>
    <Methodology>Metrics shown are sums or rates from the current supplied source release and active filters. Multiple competition records can overlap; use a single competition and season for a scoped comparison. Player IDs are provisional source-local identities, not verified global provider IDs.</Methodology>
  </>;
}

export function PlayerProfileV2Page() {
  const { playerId = '' } = useParams();
  const load = useCallback(async (signal: AbortSignal) => {
    const player = await v2Api.player(playerId, signal);
    const seasons = await v2Api.playerSeasons(playerId, signal);
    const career = await v2Api.playerCareer(playerId, signal);
    return [player, seasons, career] as const;
  }, [playerId]);
  const state = useLoad(load, [{ } as PlayerDetail, { items: [], meta: { total: 0, limit: 200, offset: 0 }, source_context: {} }, { items: [], source_context: {} }] as const);
  const [player, seasons, career] = state.data;
  return <><V2Heading eyebrow="CANONICAL PLAYER PROFILE" title={player.canonical_name || 'Player profile'}>{state.loading ? 'Loading player identity and record history.' : state.error ? 'This player profile could not be loaded.' : `${player.identity_status} identity · ${number(player.record_count)} source records across ${number(player.competition_count)} competitions and ${number(player.club_count)} clubs.`}</V2Heading>
    <div className="v2-profile-actions"><Link className="btn-outline" to="/database"><ArrowLeft size={14}/> Player explorer</Link>{!state.loading && !state.error && <Link className="btn-primary" to={`/database/compare?player=${encodeURIComponent(playerId)}`}>Add to comparison <ArrowRight size={14}/></Link>}</div>
    {state.error ? <ErrorState message={state.error} retry={state.retry}/> : state.loading ? <Loading label="Loading player identity and record history"/> : <>
      <div className="v2-profile-grid"><div className="panel v2-profile-card"><span className="eyebrow">IDENTITY</span><h2>{player.canonical_name}</h2><p>{player.primary_position ?? 'Position unavailable'} · {player.nationality ?? 'Nationality unavailable'}</p><div className="v2-context-tags"><span>{player.identity_status} identity</span><span>{player.birth_year ? `Born ${player.birth_year}` : 'Birth year unavailable'}</span><span>{player.height_cm ? `${number(player.height_cm)} cm` : 'Height unavailable'}</span></div>{player.aliases?.length > 0 && <p className="v2-muted">Aliases: {player.aliases.join(', ')}</p>}</div><div className="panel v2-profile-card"><span className="eyebrow">COVERED RECORD TOTALS</span><div className="v2-mini-metrics">{[['Minutes', player.minutes], ['Goals', player.goals], ['Assists', player.assists], ['Shots', player.shots], ['Shots on target', player.shots_on_target], ['G+A / 90', player.contributions_per90]].map(([label, value]) => <div key={String(label)}><span>{label}</span><b>{number(value as number | null, String(label).includes('/ 90') ? 2 : 0)}</b></div>)}</div></div></div>
      <Methodology>Covered-record totals may combine competition records. They describe this supplied dataset and are not full-career totals. Missing biographical or statistical observations remain unavailable.</Methodology>
      {(player.goals_against != null || player.saves != null || player.save_percent != null) && <section className="v2-section"><div className="section-head"><div><div className="eyebrow">GOALKEEPER RECORDS</div><h2>Goalkeeping statistics</h2></div></div><div className="metrics-grid compact">{[['Goals against', player.goals_against], ['Goals against / 90', player.goals_against_per90], ['Shots on target faced', player.shots_on_target_against], ['Saves', player.saves], ['Save %', player.save_percent], ['Clean sheets', player.clean_sheets]].map(([label, value]) => <div className="metric-card" key={String(label)}><div className="metric-top">{String(label).toUpperCase()}</div><div className="metric-value">{number(value as number | null, String(label).includes('/ 90') || String(label).includes('%') ? 2 : 0)}{String(label).includes('%') && value != null ? '%' : ''}</div></div>)}</div><Methodology>These are goalkeeper player-record statistics from the supplied source. They are not verified club defensive totals.</Methodology></section>}
      <section className="v2-section"><div className="section-head"><div><div className="eyebrow">SOURCE RECORDS</div><h2>Season and competition history</h2></div></div>{seasons.items.length === 0 ? <Empty>No source records are available for this player.</Empty> : <div className="panel table-panel"><div className="table-scroll"><table><caption className="sr-only">Player statistical records with competition and source provenance</caption><thead><tr><th scope="col">SEASON</th><th scope="col">COMPETITION</th><th scope="col">CLUB</th><th scope="col">MIN</th><th scope="col">G</th><th scope="col">A</th><th scope="col">SHOTS</th><th scope="col">SOT</th><th scope="col">G+A / 90</th><th scope="col">SOURCE</th></tr></thead><tbody>{seasons.items.map(record => <tr key={record.id}><td>{record.season}</td><td>{record.competition ?? '—'}</td><td>{record.club ?? '—'}</td><td>{number(record.minutes)}</td><td>{number(record.goals)}</td><td>{number(record.assists)}</td><td>{number(record.shots)}</td><td>{number(record.shots_on_target)}</td><td>{number(record.contributions_per90, 2)}</td><td>{record.source_release}</td></tr>)}</tbody></table></div></div>}</section>
      <section className="v2-section"><div className="section-head"><div><div className="eyebrow">CAREER HISTORY IN THIS SOURCE</div><h2>Season rollup</h2></div></div><div className="panel table-panel"><div className="table-scroll"><table><caption className="sr-only">Season-level sums of the player's supplied source records</caption><thead><tr><th scope="col">SEASON</th><th scope="col">RECORDS</th><th scope="col">CLUBS</th><th scope="col">COMPETITIONS</th><th scope="col">MINUTES</th><th scope="col">GOALS</th><th scope="col">ASSISTS</th></tr></thead><tbody>{career.items.map((row, index) => <tr key={`${String(row.season_id)}-${index}`}><td>{String(row.season ?? '—')}</td><td>{number(row.records as number)}</td><td>{number(row.clubs as number)}</td><td>{number(row.competitions as number)}</td><td>{number(row.minutes as number | null)}</td><td>{number(row.goals as number | null)}</td><td>{number(row.assists as number | null)}</td></tr>)}</tbody></table></div></div></section>
      <p className="v2-provenance">Source: {player.source_context?.provider_name ?? 'unavailable'} · Release: {player.source_context?.release_name ?? 'unavailable'} · Rights: {player.source_context?.rights_status ?? 'unverified'}</p>
    </>}
  </>;
}

export function ClubsPage() {
  const coverage = useCoverage(); const seasons = useSeasonOptions(); const [search, setSearch] = useState(''); const [season, setSeason] = useState(''); const [offset, setOffset] = useState(0);
  const load = useCallback((signal: AbortSignal) => v2Api.clubs({ search: search || undefined, season_id: season || undefined, limit: 50, offset }, signal), [search, season, offset]);
  const state = useLoad(load, { items: [], meta: { total: 0, limit: 50, offset: 0 } });
  return <><V2Heading eyebrow="CLUB DIRECTORY" title="Clubs in the dataset.">Explore club records, player counts, competitions, and available seasons. All displayed goal and assist totals are player-record aggregates.</V2Heading><div className="v2-toolbar"><label className="searchbox"><Search size={17}/><span className="sr-only">Search clubs</span><input value={search} onChange={event => { setSearch(event.target.value); setOffset(0); }} placeholder="Search clubs…"/></label><FilterSelect label="Season" value={season} onChange={value => { setSeason(value); setOffset(0); }} options={seasons.data.items.map(x => ({ value: x.id, label: x.label }))}/></div>{state.error && <ErrorState message={state.error} retry={state.retry}/ >}{state.loading ? <Loading/> : state.data.items.length === 0 ? <Empty>No clubs match these filters.</Empty> : <div className="v2-directory-grid">{state.data.items.map((club: Club) => <Link to={`/database/clubs/${encodeURIComponent(club.id)}`} className="panel v2-directory-card" key={club.id}><span className="eyebrow">{number(club.players)} PLAYERS · {number(club.records)} RECORDS</span><h2>{club.canonical_name}</h2><p>{club.competitions.join(' · ') || 'Competition unavailable'}</p><div className="v2-card-metrics"><span>Goals <b>{number(club.player_record_goals)}</b></span><span>Assists <b>{number(club.player_record_assists)}</b></span></div></Link>)}</div>}<div className="v2-pagination"><button className="btn-outline" disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</button><span>{number(state.data.meta.total)} clubs · season coverage {number(coverage.data.seasons.length)}</span><button className="btn-outline" disabled={offset + 50 >= state.data.meta.total} onClick={() => setOffset(offset + 50)}>Next</button></div><Methodology>Club totals are sums of the source's player rows and may contain competition overlap. They are not verified official club totals.</Methodology></>;
}

export function ClubDetailPage() {
  const { clubId = '' } = useParams(); const [season, setSeason] = useState(''); const [competition, setCompetition] = useState('');
  const clubLoad = useCallback((signal: AbortSignal) => v2Api.club(clubId, signal), [clubId]); const clubState = useLoad(clubLoad, {} as Awaited<ReturnType<typeof v2Api.club>>);
  const playerLoad = useCallback((signal: AbortSignal) => v2Api.clubPlayers(clubId, { season_id: season || undefined, competition_id: competition || undefined, limit: 100 }, signal), [clubId, season, competition]); const players = useLoad(playerLoad, { items: [], meta: { total: 0, limit: 100, offset: 0 }, source_context: {} });
  const coverage = useCoverage(); const filters = v2Filters(coverage.data, []);
  return <><V2Heading eyebrow="CLUB PROFILE" title={clubState.data.canonical_name || 'Club profile'}>Source coverage for this club across the available competitions and seasons.</V2Heading>{clubState.error && <ErrorState message={clubState.error} retry={clubState.retry}/ >}{clubState.loading ? <Loading/> : <><div className="v2-profile-actions"><Link className="btn-outline" to="/database/clubs"><ArrowLeft size={14}/> Clubs</Link></div><div className="metrics-grid compact"><div className="metric-card"><div className="metric-top">PLAYERS</div><div className="metric-value">{number(clubState.data.players)}</div></div><div className="metric-card"><div className="metric-top">PLAYER RECORDS</div><div className="metric-value">{number(clubState.data.records)}</div></div><div className="metric-card"><div className="metric-top">PLAYER GOALS</div><div className="metric-value">{number(clubState.data.player_record_goals)}</div></div><div className="metric-card"><div className="metric-top">PLAYER ASSISTS</div><div className="metric-value">{number(clubState.data.player_record_assists)}</div></div></div><Methodology>{clubState.data.methodology} Source scope is limited to imported rows.</Methodology><div className="v2-toolbar"><FilterSelect label="Season" value={season} onChange={setSeason} options={filters.seasons}/><FilterSelect label="Competition" value={competition} onChange={setCompetition} options={filters.competitions}/></div>{players.error && <ErrorState message={players.error} retry={players.retry}/ >}<PlayerTable items={players.data.items} loading={players.loading} empty="No player records match this club scope."/></>}</>;
}

function PlayerTable({ items, loading, empty }: { items: PlayerSummary[]; loading: boolean; empty: string }) {
  if (loading) return <Loading label="Loading player records"/>; if (!items.length) return <Empty>{empty}</Empty>;
  return <div className="panel table-panel"><div className="table-scroll"><table><caption className="sr-only">Player records in this selected scope</caption><thead><tr><th scope="col">PLAYER</th><th scope="col">POS</th><th scope="col">RECORDS</th><th scope="col">MIN</th><th scope="col">G</th><th scope="col">A</th><th scope="col">G+A / 90</th></tr></thead><tbody>{items.map(player => <tr key={player.id}><td><Link className="player-detail-link" to={`/database/player/${encodeURIComponent(player.id)}`}>{player.canonical_name}</Link></td><td>{player.primary_position ?? '—'}</td><td>{number(player.record_count)}</td><td>{number(player.minutes)}</td><td>{number(player.goals)}</td><td>{number(player.assists)}</td><td>{number(player.contributions_per90, 2)}</td></tr>)}</tbody></table></div></div>;
}

export function CompetitionsPage() {
  const [search, setSearch] = useState('');
  const [season, setSeason] = useState('');
  const [offset, setOffset] = useState(0);
  const seasons = useSeasonOptions();
  const load = useCallback((signal: AbortSignal) => v2Api.competitions({ search: search || undefined, season_id: season || undefined, limit: 50, offset }, signal), [search, season, offset]);
  const state = useLoad(load, { items: [], meta: { total: 0, limit: 50, offset: 0 } });
  const analyticsLoad = useCallback((signal: AbortSignal) => v2Api.competitionAnalysis(season || undefined, signal), [season]);
  const analytics = useLoad<Awaited<ReturnType<typeof v2Api.competitionAnalysis>>>(analyticsLoad, { items: [], methodology: '' });
  return <>
    <V2Heading eyebrow="COMPETITION DIRECTORY" title="Competition coverage.">Browse competition player records and compare descriptive totals from the current imported release. Coverage does not imply complete official standings.</V2Heading>
    <div className="v2-toolbar"><label className="searchbox"><Search size={17}/><span className="sr-only">Search competitions</span><input value={search} onChange={event => { setSearch(event.target.value); setOffset(0); }} placeholder="Search competitions…"/></label><FilterSelect label="Season" value={season} onChange={value => { setSeason(value); setOffset(0); }} options={seasons.data.items.map(item => ({ value: item.id, label: item.label }))}/></div>
    {state.error && <ErrorState message={state.error} retry={state.retry}/>}
    {state.loading ? <Loading/> : state.data.items.length === 0 ? <Empty>No competitions match this scope.</Empty> : <div className="v2-directory-grid">{state.data.items.map((comp: Competition) => <Link to={`/database/competitions/${encodeURIComponent(comp.id)}`} className="panel v2-directory-card" key={comp.id}><span className="eyebrow">{number(comp.players)} PLAYERS · {number(comp.clubs)} CLUBS</span><h2>{comp.canonical_name}</h2><p>{comp.seasons.join(' · ')}</p><div className="v2-card-metrics"><span>Goals <b>{number(comp.player_record_goals)}</b></span><span>Assists <b>{number(comp.player_record_assists)}</b></span></div></Link>)}</div>}
    <div className="v2-pagination"><button className="btn-outline" disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</button><span>{number(state.data.meta.total)} competitions</span><button className="btn-outline" disabled={offset + 50 >= state.data.meta.total} onClick={() => setOffset(offset + 50)}>Next</button></div>
    <section className="v2-section"><div className="section-head"><div><div className="eyebrow">PANDAS GROUPED ANALYSIS</div><h2>Competition performance comparison</h2></div></div>
      <p className="chart-description">Goals and assists per player use summed player-record statistics divided by distinct source-local players. These are descriptive dataset aggregates, not competition standings.</p>
      {analytics.error && <ErrorState message={analytics.error} retry={analytics.retry}/>}
      {analytics.loading ? <Loading label="Comparing competition player records"/> : analytics.data.items.length === 0 ? <Empty>No competition statistics are available in this season scope.</Empty> : <>
        <div className="panel chart-panel v2-chart-panel"><div className="panel-head"><div><div className="eyebrow">MEAN OUTPUT PER SOURCE-LOCAL PLAYER</div><h3>Goals and assists by competition</h3></div><span className="chart-unit">PANDAS GROUPBY</span></div><ResponsiveContainer width="100%" height={300}><BarChart data={analytics.data.items}><CartesianGrid stroke="var(--pq-grid)" vertical={false}/><XAxis dataKey="competition" tick={{ fill: 'var(--pq-text-muted)', fontSize: 10 }}/><YAxis allowDecimals tick={{ fill: 'var(--pq-text-muted)', fontSize: 10 }}/><Tooltip contentStyle={{ background: 'var(--pq-surface-2)', border: '1px solid var(--pq-line-strong)', color: 'var(--pq-text)' }}/><Legend/><Bar dataKey="goals_per_player" name="Goals per player" fill="var(--pq-series-1)" radius={[3,3,0,0]}/><Bar dataKey="assists_per_player" name="Assists per player" fill="var(--pq-series-3)" radius={[3,3,0,0]}/></BarChart></ResponsiveContainer></div>
        <div className="panel table-panel"><div className="table-scroll"><table><caption className="sr-only">Competition totals, distinct players and player-record averages; a text equivalent of the output chart</caption><thead><tr><th scope="col">COMPETITION</th><th scope="col">SEASON</th><th scope="col">PLAYERS</th><th scope="col">CLUBS</th><th scope="col">RECORDS</th><th scope="col">GOALS</th><th scope="col">ASSISTS</th><th scope="col">SHOTS</th><th scope="col">ON TARGET</th><th scope="col">AVG MIN</th><th scope="col">GOALS / PLAYER</th><th scope="col">ASSISTS / PLAYER</th></tr></thead><tbody>{analytics.data.items.map(item => <tr key={`${item.competition_id}-${item.season_id}`}><th scope="row">{item.competition}</th><td>{item.season}</td><td>{number(item.players)}</td><td>{number(item.clubs)}</td><td>{number(item.records)}</td><td>{number(item.goals)}</td><td>{number(item.assists)}</td><td>{number(item.shots)}</td><td>{number(item.shots_on_target)}</td><td>{number(item.average_minutes, 1)}</td><td>{number(item.goals_per_player, 2)}</td><td>{number(item.assists_per_player, 2)}</td></tr>)}</tbody></table></div></div>
      </>}
      {analytics.data.methodology && <Methodology>{analytics.data.methodology}</Methodology>}
    </section>
    <Methodology>Competition figures describe the supplied player records, not full official competition totals or standings.</Methodology>
  </>;
}

export function CompetitionDetailPage() {
  const { competitionId = '' } = useParams(); const [season, setSeason] = useState(''); const [position, setPosition] = useState(''); const [minimumMinutes, setMinimumMinutes] = useState(0);
  const detailLoad = useCallback((signal: AbortSignal) => v2Api.competition(competitionId, signal), [competitionId]); const detail = useLoad(detailLoad, {} as Awaited<ReturnType<typeof v2Api.competition>>);
  const playersLoad = useCallback((signal: AbortSignal) => v2Api.competitionPlayers(competitionId, { season_id: season || undefined, position: position || undefined, minimum_minutes: minimumMinutes, limit: 100 }, signal), [competitionId, season, position, minimumMinutes]); const players = useLoad(playersLoad, { items: [], meta: { total: 0, limit: 100, offset: 0 }, source_context: {} });
  const positions = usePositionOptions();
  return <><V2Heading eyebrow="COMPETITION PROFILE" title={detail.data.canonical_name || 'Competition profile'}>Source coverage, represented seasons, and a filterable player leaderboard.</V2Heading>{detail.error && <ErrorState message={detail.error} retry={detail.retry}/ >}{detail.loading ? <Loading/> : <><div className="v2-profile-actions"><Link className="btn-outline" to="/database/competitions"><ArrowLeft size={14}/> Competitions</Link></div><div className="metrics-grid compact"><div className="metric-card"><div className="metric-top">PLAYERS</div><div className="metric-value">{number(detail.data.players)}</div></div><div className="metric-card"><div className="metric-top">CLUBS</div><div className="metric-value">{number(detail.data.clubs)}</div></div><div className="metric-card"><div className="metric-top">RECORDS</div><div className="metric-value">{number(detail.data.records)}</div></div><div className="metric-card"><div className="metric-top">SEASONS</div><div className="metric-value">{number(detail.data.seasons?.length)}</div></div></div><Methodology>{detail.data.methodology}</Methodology><div className="v2-toolbar"><FilterSelect label="Season" value={season} onChange={setSeason} options={(detail.data.seasons ?? []).map(x => ({ value: x.id, label: x.label }))}/><FilterSelect label="Position" value={position} onChange={setPosition} options={positions.data.items.map(x => ({ value: x.listed_position, label: x.listed_position }))}/><FilterSelect label="Minimum minutes" value={String(minimumMinutes)} onChange={value => setMinimumMinutes(Number(value))} options={[0, 450, 900, 1800].map(x => ({ value: String(x), label: x ? `${x}+` : 'Any' }))}/></div>{players.error && <ErrorState message={players.error} retry={players.retry}/ >}<PlayerTable items={players.data.items} loading={players.loading} empty="No players match this competition scope."/></>}</>;
}

export function SeasonsPage() {
  const state = useSeasonOptions();
  return <><V2Heading eyebrow="SEASON NAVIGATION" title="Browse covered seasons.">Season records are source editions. A record count is not the same as unique players or appearances.</V2Heading>{state.error && <ErrorState message={state.error} retry={state.retry}/ >}{state.loading ? <Loading/> : state.data.items.length === 0 ? <Empty>No season coverage is available.</Empty> : <div className="v2-directory-grid">{state.data.items.map((season: Season) => <Link key={season.id} to={`/database/seasons/${encodeURIComponent(season.id)}`} className="panel v2-directory-card"><span className="eyebrow">{number(season.records)} RECORDS</span><h2>{season.label}</h2><p>{number(season.players)} players · {number(season.clubs)} clubs · {number(season.competitions)} competitions</p></Link>)}</div>}</>;
}

export function SeasonDetailPage() {
  const { seasonId = '' } = useParams(); const load = useCallback((signal: AbortSignal) => v2Api.season(seasonId, signal), [seasonId]); const state = useLoad(load, {} as Awaited<ReturnType<typeof v2Api.season>>);
  const coverage = useCoverage(); const [competition, setCompetition] = useState(''); const [position, setPosition] = useState(''); const [minimumMinutes, setMinimumMinutes] = useState(0); const positions = usePositionOptions();
  const playerLoad = useCallback((signal: AbortSignal) => v2Api.players({ season_id: seasonId, competition_id: competition || undefined, position: position || undefined, minimum_minutes: minimumMinutes, sort_by: 'goals', order: 'desc', limit: 100 }, signal), [seasonId, competition, position, minimumMinutes]); const players = useLoad(playerLoad, { items: [], meta: { total: 0, limit: 100, offset: 0 }, source_context: {} });
  const competitions = useMemo(() => coverage.data.competitions.map(x => ({ value: x.id, label: x.name })), [coverage.data.competitions]);
  return <><V2Heading eyebrow="SEASON COVERAGE" title={state.data.label || 'Season'}>Explore canonical players and their statistics within this season and selected competition.</V2Heading>{state.error && <ErrorState message={state.error} retry={state.retry}/ >}{state.loading ? <Loading/> : <><div className="v2-profile-actions"><Link className="btn-outline" to="/database/seasons"><ArrowLeft size={14}/> Seasons</Link></div><div className="metrics-grid compact"><div className="metric-card"><div className="metric-top">PLAYERS</div><div className="metric-value">{number(state.data.players)}</div></div><div className="metric-card"><div className="metric-top">CLUBS</div><div className="metric-value">{number(state.data.clubs)}</div></div><div className="metric-card"><div className="metric-top">COMPETITIONS</div><div className="metric-value">{number(state.data.competitions)}</div></div><div className="metric-card"><div className="metric-top">RECORDS</div><div className="metric-value">{number(state.data.records)}</div></div></div><div className="v2-toolbar"><FilterSelect label="Competition" value={competition} onChange={setCompetition} options={competitions}/><FilterSelect label="Position" value={position} onChange={setPosition} options={positions.data.items.map(x => ({ value: x.listed_position, label: x.listed_position }))}/><FilterSelect label="Minimum minutes" value={String(minimumMinutes)} onChange={value => setMinimumMinutes(Number(value))} options={[0, 450, 900, 1800].map(x => ({ value: String(x), label: x ? `${x}+` : 'Any' }))}/></div><PlayerTable items={players.data.items} loading={players.loading} empty="No players match this season scope."/></>}</>;
}

export function CompareV2Page() {
  const [params] = useSearchParams();
  const [search, setSearch] = useState('');
  const [ids, setIds] = useState<string[]>(() => [...new Set(params.getAll('player'))].slice(0, 4));
  const [season, setSeason] = useState('');
  const [competition, setCompetition] = useState('');
  const [minimumMinutes, setMinimumMinutes] = useState(0);
  const [result, setResult] = useState<Awaited<ReturnType<typeof v2Api.compare>> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const compareController = useRef<AbortController | null>(null);
  const candidateLoad = useCallback((signal: AbortSignal) => v2Api.players({ search: search.trim() || undefined, limit: 20, sort_by: 'name' }, signal), [search]);
  const candidates = useLoad(candidateLoad, { items: [], meta: { total: 0, limit: 20, offset: 0 }, source_context: {} });
  const coverage = useCoverage();

  const add = (playerId: string) => {
    setIds(current => current.includes(playerId) || current.length >= 4 ? current : [...current, playerId]);
    setResult(null);
  };
  const compare = async () => {
    if (!ids.length) { setError('Search for and add at least one player.'); return; }
    compareController.current?.abort();
    const controller = new AbortController();
    compareController.current = controller;
    setBusy(true);
    setError('');
    try {
      const next = await v2Api.compare({ player_ids: ids, season_id: season || undefined, competition_id: competition || undefined, minimum_minutes: minimumMinutes }, controller.signal);
      if (!controller.signal.aborted) setResult(next);
    } catch (reason) {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Comparison failed.');
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  };
  useEffect(() => () => compareController.current?.abort(), []);
  useEffect(() => { compareController.current?.abort(); setBusy(false); }, [ids, season, competition, minimumMinutes]);
  const download = async () => {
    if (!result) return;
    try {
      const blob = await v2Api.exportComparison({ player_ids: ids, season_id: season || undefined, competition_id: competition || undefined, minimum_minutes: minimumMinutes });
      saveBlob(blob, 'pitchiq_v2_comparison.csv');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Export failed.');
    }
  };
  const competitions = coverage.data.competitions.map(item => ({ value: item.id, label: item.name }));
  const seasons = coverage.data.seasons.map(item => ({ value: item.id, label: item.label }));
  const scopeLabel = [
    season ? seasons.find(item => item.value === season)?.label : '',
    competition ? competitions.find(item => item.value === competition)?.label : '',
  ].filter(Boolean).join(' · ') || 'All covered records';

  return <>
    <V2Heading eyebrow="CANONICAL PLAYER COMPARISON" title="Compare up to four players.">Select a consistent season and competition scope. Missing metrics stay unavailable; raw and per-90 values remain separate.</V2Heading>
    <div className="v2-compare-controls">
      <label className="searchbox"><Search size={17}/><span className="sr-only">Search comparison players</span><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search a player to add…"/></label>
      <div className="v2-candidate-list" aria-live="polite">
        {candidates.data.items.filter(player => !ids.includes(player.id)).slice(0, 8).map(player =>
          <button key={player.id} className="btn-outline v2-candidate" onClick={() => add(player.id)} disabled={ids.length >= 4}>
            <span>{player.canonical_name}<small>{player.primary_position ?? 'Position unavailable'} · {number(player.record_count)} records</small></span><b>+ Add</b>
          </button>)}
        {!candidates.loading && candidates.data.items.length === 0 && search.trim() && <p className="v2-muted">No players match “{search.trim()}”.</p>}
      </div>
    </div>
    <div className="v2-selected-list"><span>Selected ({ids.length}/4)</span>
      {ids.map(id => <button className="v2-selected-chip" key={id} onClick={() => { setIds(items => items.filter(item => item !== id)); setResult(null); }} aria-label={`Remove player ${id} from comparison`}>
        {candidates.data.items.find(player => player.id === id)?.canonical_name ?? id} ×
      </button>)}
      {ids.length > 0 && <button className="btn-outline" onClick={() => { setIds([]); setResult(null); }}>Clear selection</button>}
    </div>
    <div className="v2-toolbar">
      <FilterSelect label="Season" value={season} onChange={setSeason} options={seasons}/>
      <FilterSelect label="Competition" value={competition} onChange={setCompetition} options={competitions}/>
      <FilterSelect label="Minimum minutes" value={String(minimumMinutes)} onChange={value => setMinimumMinutes(Number(value))} options={[0, 450, 900, 1800].map(value => ({ value: String(value), label: value ? `${value}+` : 'Any' }))}/>
      <button className="btn-primary" disabled={busy || ids.length === 0} onClick={compare}>{busy ? 'Comparing…' : 'Compare players'}</button>
    </div>
    {error && <div className="notice" role="alert">{error}</div>}
    {busy && !result && <Loading label="Comparing selected players…"/>}
    {result && <ComparisonExperience result={result} scopeLabel={scopeLabel} onExport={download}/>}
  </>;
}

export function LeaderboardsPage() {
  const coverage = useCoverage(); const positions = usePositionOptions(); const [metric, setMetric] = useState('goals_per90'); const [season, setSeason] = useState(''); const [competition, setCompetition] = useState(''); const [position, setPosition] = useState(''); const [minutes, setMinutes] = useState(450);
  const load = useCallback((signal: AbortSignal) => v2Api.leaderboard({ metric, season_id: season || undefined, competition_id: competition || undefined, position: position || undefined, minimum_minutes: minutes, limit: 100 }, signal), [metric, season, competition, position, minutes]); const state = useLoad<Leaderboard>(load, { metric, unit: '', minimum_minutes: minutes, eligible_count: 0, percentile_method: '', items: [], methodology: '' });
  const available = coverage.data.metrics;
  const requirements: Record<string, string[]> = { goals_per90: ['goals','minutes'], assists_per90: ['assists','minutes'], contributions_per90: ['goals','assists','minutes'], non_penalty_goals_per90: ['non_penalty_goals','minutes'], non_penalty_contributions_per90: ['non_penalty_goals','assists','minutes'], shots_per90: ['shots','minutes'], shots_on_target_per90: ['shots_on_target','minutes'], crosses_per90: ['crosses','minutes'], tackles_won_per90: ['tackles_won','minutes'], interceptions_per90: ['interceptions','minutes'], goals_per_appearance: ['goals','appearances'], assists_per_appearance: ['assists','appearances'], goals_per_shot: ['goals','shots'], shots_per_goal: ['goals','shots'], shot_accuracy: ['shots','shots_on_target'] };
  const allowed = ['goals','assists','non_penalty_goals','non_penalty_goal_contributions','penalties_scored','penalties_attempted','yellow_cards','red_cards','second_yellow_cards','fouls_committed','fouls_drawn','own_goals','appearances','minutes','shots','shots_on_target','crosses','tackles_won','interceptions','goals_per90','assists_per90','contributions_per90','non_penalty_goals_per90','non_penalty_contributions_per90','shots_per90','shots_on_target_per90','crosses_per90','tackles_won_per90','interceptions_per90','goals_per_appearance','assists_per_appearance','goals_per_shot','shots_per_goal','shot_accuracy'];
  const options = Object.entries(metricLabel).filter(([key]) => allowed.includes(key) && (requirements[key] ?? [key]).every(required => available.some(row => row.metric === required && row.available_records > 0))).map(([value, label]) => ({ value, label }));
  return <>
    <V2Heading eyebrow="PERFORMANCE LEADERBOARDS" title="Rank the covered records.">Filter the eligible cohort and set a minutes floor for rate metrics. Rankings use the supplied player records, not a universal player rating.</V2Heading>
    <div className="v2-toolbar">
      <FilterSelect label="Metric" value={metric} onChange={setMetric} options={options}/>
      <FilterSelect label="Season" value={season} onChange={setSeason} options={coverage.data.seasons.map(x => ({ value: x.id, label: x.label }))}/>
      <FilterSelect label="Competition" value={competition} onChange={setCompetition} options={coverage.data.competitions.map(x => ({ value: x.id, label: x.name }))}/>
      <FilterSelect label="Position" value={position} onChange={setPosition} options={positions.data.items.map(x => ({ value: x.listed_position, label: x.listed_position }))}/>
      <FilterSelect label="Minimum minutes" value={String(minutes)} onChange={value => setMinutes(Number(value))} options={[0, 450, 900, 1800].map(x => ({ value: String(x), label: x ? `${x}+` : 'Any' }))}/>
    </div>
    {state.error && <ErrorState message={state.error} retry={state.retry}/>}
    <div className="v2-results-line"><span>{state.loading ? 'Calculating eligible cohort…' : `${number(state.data.eligible_count)} eligible players · ${metricLabel[metric] ?? metric}`}</span><a className="btn-outline export-link" href={v2Api.exportLeaderboard({ metric, season_id: season || undefined, competition_id: competition || undefined, minimum_minutes: minutes, limit: 100 })}><Download size={14}/> Export leaderboard</a></div>
    <div className="panel table-panel"><div className="table-scroll"><table><caption className="sr-only">Player leaderboard, rank, metric, and cohort-relative percentile</caption><thead><tr><th scope="col">RANK</th><th scope="col">PLAYER</th><th scope="col">POSITION</th><th scope="col">CLUBS</th><th scope="col">MINUTES</th><th scope="col">{metricLabel[metric]?.toUpperCase()}</th><th scope="col">PERCENTILE</th><th scope="col">RECORDS</th></tr></thead><tbody>{!state.loading && state.data.items.map((player, index) => <tr key={player.id}><td>{index + 1}</td><td><Link className="player-detail-link" to={`/database/player/${encodeURIComponent(player.id)}`}>{player.canonical_name}</Link></td><td>{player.primary_position ?? '—'}</td><td>{number(player.club_count)}</td><td>{number(player.minutes)}</td><td className="lime strong">{number(player[metric as keyof PlayerSummary] as number | null, metric.includes('per90') || metric.includes('per_appearance') || metric === 'shot_accuracy' || metric === 'goals_per_shot' ? 2 : 0)}{(metric === 'shot_accuracy' || metric === 'goals_per_shot') && player[metric as keyof PlayerSummary] != null ? '%' : ''}</td><td>{number(player.percentile, 1)}%</td><td>{number(player.record_count)}</td></tr>)}</tbody></table></div>{state.loading ? <Loading/> : state.data.items.length === 0 && <Empty>No players qualify in this scope. Lower the minutes threshold or broaden the filters.</Empty>}</div>
    <Methodology>{state.data.methodology} {state.data.percentile_method} The cohort and denominator change when season, competition, position, or minutes filters change.</Methodology>
  </>;
}

export function ShootingPage() {
  const coverage = useCoverage();
  const positions = usePositionOptions();
  const [season, setSeason] = useState('');
  const [competition, setCompetition] = useState('');
  const [position, setPosition] = useState('');
  const [groupBy, setGroupBy] = useState<'position' | 'competition'>('position');
  const [minutes, setMinutes] = useState(450);
  const [distribution, setDistribution] = useState<LabResult | null>(null);
  const [summary, setSummary] = useState<DescriptiveResult | null>(null);
  const [scatter, setScatter] = useState<LabResult | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);
  const run = async () => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setLoading(true);
    setError('');
    try {
      const scope = { season_id: season || undefined, competition_id: competition || undefined, position: position || undefined, minimum_minutes: minutes };
      const [histogram, stats, shotScatter] = await Promise.all([
        v2Api.dataLab({ visualization: 'histogram', metrics: ['shot_accuracy'], ...scope, limit: 1000 }, controller.signal),
        v2Api.descriptive({ ...scope, metrics: ['shots', 'shots_on_target', 'goals', 'shot_accuracy', 'goals_per_shot', 'shots_per90', 'goals_per90'], group_by: groupBy }, controller.signal),
        v2Api.dataLab({ visualization: 'scatter', metrics: ['shots', 'goals'], ...scope, limit: 1000 }, controller.signal),
      ]);
      if (!controller.signal.aborted) { setDistribution(histogram); setSummary(stats); setScatter(shotScatter); }
    } catch (reason) {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Could not calculate shooting analysis.');
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  };
  useEffect(() => { void run(); return () => controllerRef.current?.abort(); }, []);
  useEffect(() => { controllerRef.current?.abort(); setDistribution(null); setSummary(null); setScatter(null); }, [season, competition, position, groupBy, minutes]);
  const bins = distribution?.visualization === 'histogram' ? distribution.items : [];
  const shotPoints = scatter?.visualization === 'scatter' ? scatter.items : [];
  return <>
    <V2Heading eyebrow="SHOOTING ANALYTICS" title="Shooting, in context.">Explore observed shots, shots on target, goals and rate metrics. The dataset has no shot locations or shot-quality data.</V2Heading>
    <div className="v2-toolbar"><FilterSelect label="Season" value={season} onChange={setSeason} options={coverage.data.seasons.map(item => ({ value: item.id, label: item.label }))}/><FilterSelect label="Competition" value={competition} onChange={setCompetition} options={coverage.data.competitions.map(item => ({ value: item.id, label: item.name }))}/><FilterSelect label="Position" value={position} onChange={setPosition} options={positions.data.items.map(item => ({ value: item.listed_position, label: item.listed_position }))}/><FilterSelect label="Group statistics by" value={groupBy} onChange={value => setGroupBy(value as typeof groupBy)} options={[{ value: 'position', label: 'First-listed position' }, { value: 'competition', label: 'Competition' }]}/><FilterSelect label="Minimum minutes" value={String(minutes)} onChange={value => setMinutes(Number(value))} options={[0, 450, 900, 1800].map(value => ({ value: String(value), label: value ? `${value}+` : 'Any' }))}/><button className="btn-primary" onClick={() => void run()} disabled={loading}>{loading ? 'Calculating…' : 'Update analysis'}</button></div>
    {error && <div className="notice" role="alert">{error}<button className="retry-button" onClick={() => void run()}>Retry analysis</button></div>}
    {loading && <Loading label="Calculating filtered shooting statistics"/>}
    <div className="panel chart-panel v2-chart-panel"><div className="panel-head"><div><div className="eyebrow">SHOTS ON TARGET / TOTAL SHOTS</div><h3>Shooting accuracy distribution</h3></div><span className="chart-unit">{number(distribution?.visualization === 'histogram' ? distribution.n : 0)} OBSERVATIONS</span></div><p className="chart-description">Shooting accuracy = shots on target ÷ total shots × 100; a valid source SoT% value is retained when present. This is not goals ÷ shots conversion.</p>{bins.length === 0 ? <Empty>No valid shooting accuracy observations qualify in this scope.</Empty> : <ResponsiveContainer width="100%" height={290}><BarChart data={bins.map(bin => ({ ...bin, interval: `${number(bin.from, 0)}–${number(bin.to, 0)}%` }))}><CartesianGrid stroke="var(--pq-grid)" vertical={false}/><XAxis dataKey="interval" tick={{ fill: 'var(--pq-text-muted)', fontSize: 10 }}/><YAxis allowDecimals={false} tick={{ fill: 'var(--pq-text-muted)', fontSize: 10 }}/><Tooltip contentStyle={{ background: 'var(--pq-surface-2)', border: '1px solid var(--pq-line-strong)', color: 'var(--pq-text)' }}/><Bar dataKey="count" name="Player records" fill="var(--pq-series-1)" radius={[3,3,0,0]}/></BarChart></ResponsiveContainer>}</div>
    {summary && <section className="panel chart-panel v2-chart-panel"><div className="panel-head"><div><div className="eyebrow">DESCRIPTIVE SHOOTING METRICS</div><h3>Rates and sample size</h3></div><span className="chart-unit">{number(summary.record_count)} MATCHING RECORDS</span></div><div className="table-scroll"><table><caption className="sr-only">Shooting metrics calculated from valid values for the selected record scope</caption><thead><tr><th scope="col">METRIC</th><th scope="col">N</th><th scope="col">MEAN</th><th scope="col">MEDIAN</th><th scope="col">Q1</th><th scope="col">Q3</th></tr></thead><tbody>{summary.summary.map(item => <tr key={item.metric}><th scope="row">{metricLabel[item.metric] ?? item.metric}</th><td>{number(item.count)}</td><td>{number(item.mean, 3)}</td><td>{number(item.median, 3)}</td><td>{number(item.q1, 3)}</td><td>{number(item.q3, 3)}</td></tr>)}</tbody></table></div>
      {summary.groups.length > 0 && <div className="v2-chart-table"><h4>Comparison by {groupBy}</h4><div className="table-scroll"><table><caption className="sr-only">Group summaries by first-listed position or competition</caption><thead><tr><th scope="col">GROUP</th><th scope="col">PLAYERS</th><th scope="col">RECORDS</th><th scope="col">SHOTS / 90 MEAN</th><th scope="col">ACCURACY MEAN</th><th scope="col">CONVERSION MEAN</th></tr></thead><tbody>{summary.groups.map(group => { const metric = (key: string) => group.metrics.find(item => item.metric === key); return <tr key={group.group}><th scope="row">{group.group}</th><td>{number(group.player_count)}</td><td>{number(group.record_count)}</td><td>{number(metric('shots_per90')?.mean, 3)}</td><td>{number(metric('shot_accuracy')?.mean, 2)}%</td><td>{number(metric('goals_per_shot')?.mean, 2)}%</td></tr>; })}</tbody></table></div></div>}
      <Methodology>Goals per shot is a conversion rate; shooting accuracy is shots on target divided by shots. Means exclude metric-specific missing observations. Grouping keeps player records and distinguishes distinct source-local players.</Methodology>
    </section>}
    {scatter && <section className="panel chart-panel v2-chart-panel"><div className="panel-head"><div><div className="eyebrow">SHOT VOLUME AND OUTCOME</div><h3>Shots versus goals</h3></div><span className="chart-unit">{number(scatter.visualization === 'scatter' ? scatter.total : 0)} PAIRED RECORDS</span></div><p className="chart-description">Each point is a player-stat record with both fields observed; this chart does not show shot location or expected goals.</p>{shotPoints.length ? <><ResponsiveContainer width="100%" height={310}><ScatterChart><CartesianGrid stroke="var(--pq-grid)"/><XAxis type="number" dataKey="x" name="Shots" tick={{ fill: 'var(--pq-text-muted)', fontSize: 10 }}/><YAxis type="number" dataKey="y" name="Goals" tick={{ fill: 'var(--pq-text-muted)', fontSize: 10 }}/><Tooltip contentStyle={{ background: 'var(--pq-surface-2)', border: '1px solid var(--pq-line-strong)', color: 'var(--pq-text)' }}/><Scatter name="Player-stat records" data={shotPoints} fill="var(--pq-series-1)"/></ScatterChart></ResponsiveContainer><div className="table-scroll"><table><caption className="sr-only">Text alternative for the bounded shots versus goals chart</caption><thead><tr><th scope="col">PLAYER</th><th scope="col">CLUB</th><th scope="col">SHOTS</th><th scope="col">GOALS</th></tr></thead><tbody>{shotPoints.slice(0, 100).map((point, index) => <tr key={`${point.player_id}-${index}`}><th scope="row">{point.player}</th><td>{point.club ?? '—'}</td><td>{number(point.x)}</td><td>{number(point.y)}</td></tr>)}</tbody></table></div></> : <Empty>No paired shot and goal observations qualify in this scope.</Empty>}</section>}
    <div className="metrics-grid compact">{coverage.data.metrics.filter(item => ['shots', 'shots_on_target', 'source_sot_percent'].includes(item.metric)).map(item => <div className="metric-card" key={item.metric}><div className="metric-top">{metricLabel[item.metric] ?? item.metric}</div><div className="metric-value">{number(item.available_records)}</div><div className="metric-sub">of {number(item.total_records)} records · {item.status}</div></div>)}</div>
    <Methodology>No xG, shot map, or shot-quality claims are available from this source.</Methodology>
  </>;
}

type DataLabMode = LabPayload['visualization'] | 'bar' | 'line' | 'boxplot' | 'correlation_heatmap' | 'outliers';
const isLabVisualization = (value: DataLabMode): value is LabPayload['visualization'] =>
  value === 'table' || value === 'histogram' || value === 'scatter' || value === 'correlation';
const dataLabModes: DataLabMode[] = ['table', 'histogram', 'scatter', 'correlation', 'bar', 'line', 'boxplot', 'correlation_heatmap', 'outliers'];
const dataLabModeForLocation = (pathname: string, search: string): DataLabMode => {
  const requested = new URLSearchParams(search).get('visualization');
  if (requested && dataLabModes.includes(requested as DataLabMode)) return requested as DataLabMode;
  return pathname.endsWith('/descriptive') ? 'table'
    : pathname.endsWith('/correlation') ? 'correlation'
      : pathname.endsWith('/distributions') ? 'outliers' : 'histogram';
};

export function DataLabPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const coverage = useCoverage();
  const positions = usePositionOptions();
  const metricsLoad = useCallback((signal: AbortSignal) => v2Api.metrics(signal), []);
  const metrics = useLoad(metricsLoad, { items: [], available_metrics: [], unsupported: [] });
  const [visualization, setVisualization] = useState<DataLabMode>(() => dataLabModeForLocation(location.pathname, location.search));
  const [metricA, setMetricA] = useState('goals_per90');
  const [metricB, setMetricB] = useState('assists_per90');
  const [heatmapMetrics, setHeatmapMetrics] = useState<string[]>(['goals', 'assists', 'shots', 'minutes']);
  const [season, setSeason] = useState('');
  const [competition, setCompetition] = useState('');
  const [club, setClub] = useState('');
  const [position, setPosition] = useState('');
  const [groupBy, setGroupBy] = useState<'position' | 'competition' | 'club' | 'season'>('competition');
  const [method, setMethod] = useState<'pearson' | 'spearman'>('pearson');
  const [minimumMinutes, setMinimumMinutes] = useState(450);
  const [result, setResult] = useState<LabResult | null>(null);
  const [descriptive, setDescriptive] = useState<DescriptiveResult | null>(null);
  const [outliers, setOutliers] = useState<OutlierResult | null>(null);
  const [chartUrl, setChartUrl] = useState('');
  const [chartBlob, setChartBlob] = useState<Blob | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);
  const chartUrlRef = useRef<string | null>(null);
  const supported = metrics.data.items.filter(item => metrics.data.available_metrics.includes(item.metric_key));
  const oneMetric = ['histogram', 'bar', 'line', 'boxplot', 'outliers'].includes(visualization);
  const selectedMetrics = oneMetric ? [metricA] : visualization === 'correlation_heatmap' ? heatmapMetrics : [metricA, metricB];
  const metricsValid = visualization !== 'correlation_heatmap' || heatmapMetrics.length >= 2;
  const pageView = location.pathname.endsWith('/descriptive') ? 'descriptive'
    : location.pathname.endsWith('/correlation') ? 'correlation'
      : location.pathname.endsWith('/distributions') ? 'distribution' : 'lab';
  const heading = pageView === 'descriptive' ? 'Describe the selected cohort.'
    : pageView === 'correlation' ? 'Explore metric relationships.'
      : pageView === 'distribution' ? 'See the spread. Review the outliers.' : 'Ask the data a question.';
  const description = pageView === 'descriptive'
    ? 'Summarize the selected metric, compare groups, and inspect the observed sample before exporting results.'
    : pageView === 'correlation'
      ? 'Compare Pearson linear association or Spearman rank association. Correlation is descriptive and does not imply causation.'
      : pageView === 'distribution'
        ? 'Inspect value distributions and IQR flags. Unusual records remain in the dataset and are not assumed to be errors.'
        : 'Filter source records, choose a metric and visualization, then review the summary and export the result.';
  const activeScopeFilters: ActiveFilter[] = [
    ...(season ? [{ name: 'Season', value: coverage.data.seasons.find(item => item.id === season)?.label ?? season, onRemove: () => setSeason('') }] : []),
    ...(competition ? [{ name: 'Competition', value: coverage.data.competitions.find(item => item.id === competition)?.name ?? competition, onRemove: () => setCompetition('') }] : []),
    ...(club ? [{ name: 'Club', value: coverage.data.clubs.find(item => item.id === club)?.name ?? club, onRemove: () => setClub('') }] : []),
    ...(position ? [{ name: 'Position', value: position, onRemove: () => setPosition('') }] : []),
    ...(minimumMinutes ? [{ name: 'Minutes', value: `${minimumMinutes}+`, onRemove: () => setMinimumMinutes(0) }] : []),
  ];
  const changeVisualization = (value: string) => {
    const next = value as DataLabMode;
    setVisualization(next);
    navigate(`/database/data-lab?visualization=${encodeURIComponent(next)}`, { replace: true });
  };
  const scope = {
    season_id: season || undefined,
    competition_id: competition || undefined,
    club_id: club || undefined,
    position: position || undefined,
    minimum_minutes: minimumMinutes,
  };
  const discardChart = () => {
    if (chartUrlRef.current) URL.revokeObjectURL(chartUrlRef.current);
    chartUrlRef.current = null;
    setChartUrl('');
    setChartBlob(null);
  };
  const run = async () => {
    controllerRef.current?.abort();
    discardChart();
    const controller = new AbortController();
    controllerRef.current = controller;
    setLoading(true);
    setError('');
    setResult(null);
    setDescriptive(null);
    setOutliers(null);
    const summaryPayload = { ...scope, metrics: selectedMetrics, group_by: groupBy };
    try {
      const summaryPromise = v2Api.descriptive(summaryPayload, controller.signal);
      const summary = await summaryPromise;
      if (controller.signal.aborted) return;
      setDescriptive(summary);
      if (isLabVisualization(visualization)) {
        const nextPromise = v2Api.dataLab({
          visualization, metrics: selectedMetrics, method,
          ...scope, limit: 1000,
        }, controller.signal);
        const pngPromise = visualization === 'histogram' || visualization === 'scatter'
          ? v2Api.visualization({ visualization, metrics: selectedMetrics, group_by: groupBy, method, ...scope }, controller.signal)
          : Promise.resolve(null);
        const [next, image] = await Promise.all([nextPromise, pngPromise]);
        if (!controller.signal.aborted) {
          setResult(next);
          if (image) {
            const url = URL.createObjectURL(image);
            chartUrlRef.current = url;
            setChartUrl(url);
            setChartBlob(image);
          }
        }
      } else {
        let chartKind: VisualizationKind;
        switch (visualization) {
          case 'outliers':
          case 'boxplot': chartKind = 'boxplot'; break;
          case 'bar': chartKind = 'bar'; break;
          case 'line': chartKind = 'line'; break;
          case 'correlation_heatmap': chartKind = 'correlation_heatmap'; break;
          default: chartKind = 'boxplot';
        }
        const chartPayload: VisualizationPayload = {
          visualization: chartKind, metrics: selectedMetrics, group_by: groupBy, method, ...scope,
        };
        const pendingOutliers = visualization === 'outliers'
          ? v2Api.outliers({ metric: metricA, ...scope, limit: 100 }, controller.signal)
          : Promise.resolve(null);
        const [image, outlierResult] = await Promise.all([
          v2Api.visualization(chartPayload, controller.signal), pendingOutliers,
        ]);
        if (!controller.signal.aborted) {
          const url = URL.createObjectURL(image);
          chartUrlRef.current = url;
          setChartUrl(url);
          setChartBlob(image);
          setOutliers(outlierResult);
        }
      }
    } catch (reason) {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'The analysis could not be completed.');
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  };
  const exportResult = async () => {
    if (!descriptive) return;
    try {
      if (visualization === 'outliers') {
        const blob = await v2Api.exportOutliers({ metric: metricA, ...scope, limit: 5000 });
        saveBlob(blob, 'pitchiq_v2_potential_outliers.csv');
      } else if (result && isLabVisualization(visualization)) {
        const blob = await v2Api.exportDataLab({
          visualization, metrics: selectedMetrics, method,
          ...scope, limit: 1000,
        });
        saveBlob(blob, `pitchiq_v2_data_lab_${visualization}.csv`);
      } else {
        const blob = await v2Api.exportDescriptive({ ...scope, metrics: selectedMetrics, group_by: groupBy });
        saveBlob(blob, 'pitchiq_v2_analytics_summary.csv');
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The result export failed.');
    }
  };
  useEffect(() => () => {
    controllerRef.current?.abort();
    if (chartUrlRef.current) URL.revokeObjectURL(chartUrlRef.current);
  }, []);
  useEffect(() => { setVisualization(dataLabModeForLocation(location.pathname, location.search)); }, [location.pathname, location.search]);
  useEffect(() => {
    controllerRef.current?.abort();
    setLoading(false);
    setResult(null);
    setDescriptive(null);
    setOutliers(null);
    discardChart();
  }, [visualization, metricA, metricB, heatmapMetrics, season, competition, club, position, groupBy, method, minimumMinutes]);
  const histogramData = result?.visualization === 'histogram'
    ? result.items.map(item => ({ ...item, interval: `${number(item.from, 2)}–${number(item.to, 2)}` }))
    : [];
  const scatterData = result?.visualization === 'scatter' ? result.items : [];
  const tableData = result?.visualization === 'table' ? result.items : [];
  const count = descriptive?.record_count ?? (result?.visualization === 'histogram' || result?.visualization === 'correlation' ? result.n : result?.total) ?? 0;
  return <>
    <V2Heading eyebrow={pageView === 'lab' ? 'CONTROLLED ANALYTICS WORKSPACE' : 'ANALYTICAL WORKSPACE'} title={heading}>
      {description}
    </V2Heading>
    <section className="v2-analysis-builder" aria-label="Analysis setup">
      <div className="v2-builder-step">
        <div className="v2-builder-heading"><span>01 / DATASET SCOPE</span><p>Choose the source slice used in every result.</p></div>
        <div className="v2-scope-primary">
          <FilterSelect label="Season" value={season} onChange={setSeason} options={coverage.data.seasons.map(item => ({ value: item.id, label: item.label }))}/>
          <FilterSelect label="Competition" value={competition} onChange={setCompetition} options={coverage.data.competitions.map(item => ({ value: item.id, label: item.name }))}/>
        </div>
        <details className="v2-advanced-scope">
          <summary>More scope filters <span>{[club, position].filter(Boolean).length ? `${[club, position].filter(Boolean).length} selected` : 'Club, position and minutes'}</span></summary>
          <div className="v2-scope-advanced">
            <FilterSelect label="Club" value={club} onChange={setClub} options={coverage.data.clubs.map(item => ({ value: item.id, label: item.name }))}/>
            <FilterSelect label="Position" value={position} onChange={setPosition} options={positions.data.items.map(item => ({ value: item.listed_position, label: item.listed_position }))}/>
            <FilterSelect label="Minimum minutes" value={String(minimumMinutes)} onChange={value => setMinimumMinutes(Number(value))} options={[0, 450, 900, 1800].map(value => ({ value: String(value), label: value ? `${value}+` : 'Any' }))}/>
            <button type="button" className="btn-outline" onClick={() => { setSeason(''); setCompetition(''); setClub(''); setPosition(''); setMinimumMinutes(450); }}>Reset scope</button>
          </div>
        </details>
        <ActiveFilters items={activeScopeFilters}/>
      </div>
      <div className="v2-builder-step">
        <div className="v2-builder-heading"><span>02 / ANALYSIS</span><p>Select a question, metric and chart before running it.</p></div>
        <div className="v2-lab-controls">
          <FilterSelect label="Visualization" value={visualization} onChange={changeVisualization} options={[
            ['table', 'Descriptive table'], ['histogram', 'Histogram'], ['scatter', 'Scatter plot'], ['correlation', 'Correlation'],
            ['bar', 'Grouped bar chart'], ['line', 'Grouped line chart'], ['boxplot', 'Box plot'],
            ['outliers', 'Outlier review'], ['correlation_heatmap', 'Correlation heatmap'],
          ].map(([value, label]) => ({ value, label }))}/>
          <FilterSelect label="First metric" value={metricA} onChange={setMetricA} options={supported.map(item => ({ value: item.metric_key, label: item.display_name }))}/>
          {visualization === 'correlation_heatmap' ? <label className="v2-control v2-multi-select"><span>Heatmap metrics</span><select multiple size={4} value={heatmapMetrics} onChange={event => { const values = Array.from(event.currentTarget.selectedOptions, option => option.value); if (values.length <= 8) setHeatmapMetrics(values); }} aria-describedby="heatmap-metric-help">{supported.map(item => <option key={item.metric_key} value={item.metric_key}>{item.display_name}</option>)}</select><small id="heatmap-metric-help">Select 2–8 metrics</small></label> : !oneMetric && <FilterSelect label="Second metric" value={metricB} onChange={setMetricB} options={supported.filter(item => item.metric_key !== metricA).map(item => ({ value: item.metric_key, label: item.display_name }))}/>}
          {['correlation', 'correlation_heatmap'].includes(visualization) && <FilterSelect label="Correlation method" value={method} onChange={value => setMethod(value as typeof method)} options={[{ value: 'pearson', label: 'Pearson' }, { value: 'spearman', label: 'Spearman rank' }]}/ >}
          <FilterSelect label="Group results by" value={groupBy} onChange={value => setGroupBy(value as typeof groupBy)} options={[
            { value: 'competition', label: 'Competition' }, { value: 'position', label: 'First-listed position' },
            { value: 'club', label: 'Club' }, { value: 'season', label: 'Season' },
          ]}/>
          <button className="btn-primary v2-run-analysis" onClick={() => void run()} disabled={loading || !metricsValid}>{loading ? 'Calculating…' : 'Run analysis'}</button>
        </div>
      </div>
    </section>
    {!metricsValid && <p className="v2-muted" role="status">Choose at least two metrics for a correlation heatmap.</p>}
    {error && <div className="notice" role="alert">{error}<button className="retry-button" onClick={() => void run()}>Retry analysis</button></div>}
    {loading && <Loading label="Calculating from the selected database scope"/>}
    {descriptive && <section className="panel chart-panel v2-chart-panel">
      <div className="panel-head"><div><div className="eyebrow">FILTERED RECORD SUMMARY</div><h3>{selectedMetrics.map(key => metrics.data.items.find(item => item.metric_key === key)?.display_name ?? metricLabel[key] ?? key).join(' · ')}</h3></div>
        <div className="v2-chart-actions"><span className="chart-unit">{number(count)} MATCHING RECORDS</span>
          <button className="btn-outline" onClick={() => void exportResult()}><Download size={14}/> Export CSV</button>
          {chartBlob && <button className="btn-outline" onClick={() => saveBlob(chartBlob, `pitchiq_${visualization}.png`)}><Download size={14}/> Export PNG</button>}
        </div>
      </div>
      {descriptive.record_count === 0 && <Empty>No player-stat records match this filter scope. Clear one or more filters and run the analysis again.</Empty>}
      <div className="table-scroll"><table><caption className="sr-only">Descriptive summary for selected metrics; missing values are excluded metric by metric.</caption><thead><tr><th scope="col">METRIC</th><th scope="col">N</th><th scope="col">MEAN</th><th scope="col">MEDIAN</th><th scope="col">SAMPLE SD</th><th scope="col">VARIANCE</th><th scope="col">MIN</th><th scope="col">Q1</th><th scope="col">Q2</th><th scope="col">Q3</th><th scope="col">IQR</th><th scope="col">MAX</th></tr></thead>
        <tbody>{descriptive.summary.map(item => <tr key={item.metric}><th scope="row">{metricLabel[item.metric] ?? item.metric}</th><td>{number(item.count)}</td><td>{number(item.mean, 3)}</td><td>{number(item.median, 3)}</td><td>{number(item.standard_deviation, 3)}</td><td>{number(item.variance, 3)}</td><td>{number(item.minimum, 3)}</td><td>{number(item.q1, 3)}</td><td>{number(item.q2, 3)}</td><td>{number(item.q3, 3)}</td><td>{number(item.interquartile_range, 3)}</td><td>{number(item.maximum, 3)}</td></tr>)}</tbody>
      </table></div>
      {descriptive.groups.length > 0 && <div className="v2-chart-table"><h4>Grouped summary · {descriptive.group_by}</h4><div className="table-scroll"><table><caption className="sr-only">Summary by selected group; player counts are distinct source-local identities.</caption><thead><tr><th scope="col">GROUP</th><th scope="col">PLAYERS</th><th scope="col">RECORDS</th><th scope="col">METRIC</th><th scope="col">OBSERVED</th><th scope="col">MEAN</th><th scope="col">MEDIAN</th></tr></thead><tbody>{descriptive.groups.flatMap(group => group.metrics.map(item => <tr key={`${group.group}-${item.metric}`}><th scope="row">{group.group}</th><td>{number(group.player_count)}</td><td>{number(group.record_count)}</td><td>{metricLabel[item.metric] ?? item.metric}</td><td>{number(item.count)}</td><td>{number(item.mean, 3)}</td><td>{number(item.median, 3)}</td></tr>))}</tbody></table></div></div>}
      {result?.visualization === 'histogram' && (result.n > 0 ? <ResponsiveContainer width="100%" height={300}><BarChart data={histogramData}><CartesianGrid stroke="var(--pq-grid)" vertical={false}/><XAxis dataKey="interval" tick={{ fill: 'var(--pq-text-muted)', fontSize: 10 }}/><YAxis allowDecimals={false} tick={{ fill: 'var(--pq-text-muted)', fontSize: 10 }}/><Tooltip contentStyle={{ background: 'var(--pq-surface-2)', border: '1px solid var(--pq-line-strong)', color: 'var(--pq-text)' }}/><Bar dataKey="count" name="Records" fill="var(--pq-series-1)" radius={[3,3,0,0]}/></BarChart></ResponsiveContainer> : <Empty>No observed values qualify for this histogram.</Empty>)}
      {result?.visualization === 'scatter' && (scatterData.length > 0 ? <><div className="v2-chart-description">Each dot is a player-stat record. The table below provides a text alternative for the bounded plotted sample.</div><ResponsiveContainer width="100%" height={320}><ScatterChart><CartesianGrid stroke="var(--pq-grid)"/><XAxis type="number" dataKey="x" name={metricLabel[result.metrics[0]] ?? result.metrics[0]} tick={{ fill: 'var(--pq-text-muted)', fontSize: 10 }}/><YAxis type="number" dataKey="y" name={metricLabel[result.metrics[1]] ?? result.metrics[1]} tick={{ fill: 'var(--pq-text-muted)', fontSize: 10 }}/><Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ background: 'var(--pq-surface-2)', border: '1px solid var(--pq-line-strong)', color: 'var(--pq-text)' }}/><Scatter name="Player records" data={scatterData} fill="var(--pq-series-1)"/></ScatterChart></ResponsiveContainer><div className="v2-chart-table"><div className="table-scroll"><table><caption className="sr-only">Text equivalent for all scatter plot data points</caption><thead><tr><th scope="col">PLAYER</th><th scope="col">CLUB</th><th scope="col">{metricLabel[result.metrics[0]] ?? result.metrics[0]}</th><th scope="col">{metricLabel[result.metrics[1]] ?? result.metrics[1]}</th></tr></thead><tbody>{scatterData.map((item, index) => <tr key={`${item.player_id}-${index}`}><th scope="row">{item.player}</th><td>{item.club ?? '—'}</td><td>{number(item.x, 3)}</td><td>{number(item.y, 3)}</td></tr>)}</tbody></table></div></div></> : <Empty>No paired observations qualify for this scatter plot.</Empty>)}
      {result?.visualization === 'correlation' && <div className="v2-correlation-value"><b>{result.value == null ? '—' : number(result.value, 4)}</b><span>{result.unit} · n = {number(result.n)}</span><p>{result.interpretation}</p><p>{result.note}</p></div>}
      {result?.visualization === 'table' && (tableData.length ? <div className="table-scroll"><table><caption className="sr-only">Result rows for selected metrics and scope</caption><thead><tr><th scope="col">PLAYER</th><th scope="col">CLUB</th><th scope="col">COMPETITION</th><th scope="col">SEASON</th>{result.metrics.map(key => <th scope="col" key={key}>{metricLabel[key] ?? key}</th>)}</tr></thead><tbody>{tableData.map((item, index) => <tr key={`${item.player_id}-${index}`}><th scope="row">{item.player}</th><td>{item.club ?? '—'}</td><td>{item.competition ?? '—'}</td><td>{item.season}</td>{result.metrics.map(key => <td key={key}>{number(item.values[key], 3)}</td>)}</tr>)}</tbody></table></div> : <Empty>No observed rows qualify in this scope.</Empty>)}
      {chartUrl && <div className="v2-generated-chart"><img src={chartUrl} alt={`${visualization.replace(/_/g, ' ')} generated from the selected filtered metrics`}/></div>}
      {visualization === 'line' && <p className="v2-provenance">This line connects category means for visual comparison. It does not represent a time trend.</p>}
      {visualization === 'outliers' && outliers && <><div className="v2-correlation-value"><b>{number(outliers.outlier_count)}</b><span>Potential IQR outliers · Q1 {number(outliers.q1, 3)} · Q3 {number(outliers.q3, 3)} · IQR {number(outliers.iqr, 3)}</span><p>Fences: {number(outliers.lower_bound, 3)} to {number(outliers.upper_bound, 3)} ({number(outliers.multiplier, 1)} × IQR). An unusual value is not necessarily an error; records are retained.</p></div>{outliers.items.length ? <div className="table-scroll"><table><caption className="sr-only">Potential outliers ordered by distance from the IQR fence</caption><thead><tr><th scope="col">PLAYER</th><th scope="col">POSITION</th><th scope="col">CLUB</th><th scope="col">COMPETITION</th><th scope="col">SEASON</th><th scope="col">{metricLabel[metricA] ?? metricA}</th></tr></thead><tbody>{outliers.items.map(item => <tr key={item.record_id}><th scope="row">{item.player}</th><td>{item.position_raw ?? '—'}</td><td>{item.club ?? '—'}</td><td>{item.competition ?? '—'}</td><td>{item.season}</td><td>{number(typeof item[metricA] === 'number' ? item[metricA] : null, 3)}</td></tr>)}</tbody></table></div> : <Empty>No potential outlier records qualify in this scope.</Empty>}</>}
      {result && 'total' in result && result.total > result.items.length && <p className="v2-provenance">Showing {number(result.items.length)} of {number(result.total)} qualifying records. The table and scatter sample is capped at 1,000 records.</p>}
      <Methodology>{descriptive.methodology} Correlation is descriptive and does not establish causation or statistical significance. Position groups use the source’s first-listed position. IQR flags unusual observations and never removes records.</Methodology>
      <p className="v2-provenance">Source release: {result?.source_context?.release_name ?? coverage.data.source_context.release_name ?? 'unavailable'} · Rights: {result?.source_context?.rights_status ?? coverage.data.source_context.rights_status ?? 'unverified'}</p>
    </section>}
    <div className="v2-unavailable"><h3>Unavailable metrics</h3><p>The supplied data does not include xG, xA, passing attempts/completions, blocks, clearances, or aerial duels. They are not selectable.</p><div>{metrics.data.unsupported.map(value => <span key={value}>{value.replace(/_/g, ' ')}</span>)}</div></div>
  </>;
}

export function CoveragePage() {
  const coverage = useCoverage(); const sourcesLoad = useCallback((signal: AbortSignal) => v2Api.sources(signal), []); const sources = useLoad(sourcesLoad, { items: [], note: '' });
  const qualityLoad = useCallback((signal: AbortSignal) => v2Api.quality(signal), []);
  const quality = useLoad<AnalyticsQuality>(qualityLoad, { total_records: 0, total_columns: 0, missing_cells: 0, completeness_percent: null, duplicate_source_key_records: 0, duplicate_content_records: 0, potential_invalid_values: {}, numeric_columns: [], categorical_columns: [], columns: [], methodology: '' });
  const [qualityImageUrl, setQualityImageUrl] = useState(''); const [qualityImageBlob, setQualityImageBlob] = useState<Blob | null>(null); const [qualityImageLoading, setQualityImageLoading] = useState(false); const [qualityImageError, setQualityImageError] = useState(''); const qualityImageController = useRef<AbortController | null>(null); const qualityImageUrlRef = useRef<string | null>(null);
  const generateQualityImage = async () => { qualityImageController.current?.abort(); const controller = new AbortController(); qualityImageController.current = controller; setQualityImageLoading(true); setQualityImageError(''); try { const blob = await v2Api.qualityVisualization(controller.signal); if (controller.signal.aborted) return; if (qualityImageUrlRef.current) URL.revokeObjectURL(qualityImageUrlRef.current); const url = URL.createObjectURL(blob); qualityImageUrlRef.current = url; setQualityImageUrl(url); setQualityImageBlob(blob); } catch (reason) { if (!controller.signal.aborted) setQualityImageError(reason instanceof Error ? reason.message : 'The quality visualization could not be generated.'); } finally { if (!controller.signal.aborted) setQualityImageLoading(false); } };
  useEffect(() => () => { qualityImageController.current?.abort(); if (qualityImageUrlRef.current) URL.revokeObjectURL(qualityImageUrlRef.current); }, []);
  const identityLoad = useCallback((signal: AbortSignal) => v2Api.identitySummary(signal), []);
  const identity = useLoad<IdentitySummary>(identityLoad, { source_local_keys: 0, verified_external_ids: 0, decision_statuses: {}, ambiguous_name_groups: 0, ambiguity_examples: [], note: '' });
  const reviewLoad = useCallback((signal: AbortSignal) => v2Api.identityReview('needs_review', signal), []);
  const review = useLoad(reviewLoad, [] as Awaited<ReturnType<typeof v2Api.identityReview>>);
  return <>
    <V2Heading eyebrow="DATA SOURCES AND COVERAGE" title="Know what the data contains.">Coverage describes the current local release only. Public availability does not establish redistribution, display, or commercial rights.</V2Heading>
    {coverage.error && <ErrorState message={coverage.error} retry={coverage.retry}/>}
    {coverage.loading ? <Loading/> : <>
      <div className="metrics-grid compact">
        <div className="metric-card"><div className="metric-top">CANONICAL PLAYERS</div><div className="metric-value">{number(coverage.data.player_count)}</div></div>
        <div className="metric-card"><div className="metric-top">STAT RECORDS</div><div className="metric-value">{number(coverage.data.record_count)}</div></div>
        <div className="metric-card"><div className="metric-top">CLUBS</div><div className="metric-value">{number(coverage.data.clubs.length)}</div></div>
        <div className="metric-card"><div className="metric-top">COMPETITIONS</div><div className="metric-value">{number(coverage.data.competitions.length)}</div></div>
      </div>
      <section className="v2-section"><div className="section-head"><div><div className="eyebrow">SOURCE RIGHTS</div><h2>Provider and release</h2></div></div>
        {sources.error && <ErrorState message={sources.error} retry={sources.retry}/>}
        {sources.data.items.map((source, index) => <div className="panel v2-source-card" key={String(source.id ?? index)}><h3>{String(source.provider_name ?? 'Unknown source')}</h3><p>{String(source.release_name ?? 'No release imported')} · {String(source.file_name ?? 'file unavailable')}</p><span className="v2-status">Rights: {String(source.rights_status ?? 'unverified')}</span><p className="v2-muted">License: {String(source.license_name ?? 'Not documented')} · Redistribution: {String(source.redistribution_allowed ?? 'unverified')} · Commercial use: {String(source.commercial_use_allowed ?? 'unverified')}</p><code>SHA-256 {String(source.checksum ?? 'unavailable')}</code></div>)}
      </section>
      <section className="v2-section"><div className="section-head"><div><div className="eyebrow">IDENTITY QUALITY</div><h2>Local identity evidence</h2></div></div>
        {identity.error && <ErrorState message={identity.error} retry={identity.retry}/>}
        {identity.loading ? <Loading label="Checking identity evidence"/> : <>
          <div className="metrics-grid compact">
            <div className="metric-card"><div className="metric-top">SOURCE-LOCAL KEYS</div><div className="metric-value">{number(identity.data.source_local_keys)}</div></div>
            <div className="metric-card"><div className="metric-top">VERIFIED PROVIDER IDS</div><div className="metric-value">{number(identity.data.verified_external_ids)}</div></div>
            <div className="metric-card"><div className="metric-top">NAME COLLISION GROUPS</div><div className="metric-value">{number(identity.data.ambiguous_name_groups)}</div></div>
            <div className="metric-card"><div className="metric-top">PENDING REVIEW</div><div className="metric-value">{review.loading ? '…' : number(review.data.length)}</div></div>
          </div>
          <p className="chart-description">{identity.data.note}</p>
          {identity.data.ambiguity_examples.length > 0 && <div className="panel v2-identity-list"><h3>Same-name candidates, kept separate</h3>{identity.data.ambiguity_examples.map(group => <div className="v2-identity-group" key={group.normalized_name}><b>{group.normalized_name} <small>{group.candidate_count} source-local entities</small></b><div>{group.candidates.map(candidate => <span key={candidate.id}>{candidate.canonical_name} · {candidate.birth_year ?? 'birth year unknown'} · {candidate.nationality ?? 'nationality unknown'} · {candidate.identity_status}</span>)}</div></div>)}</div>}
          {review.error && <ErrorState message={review.error} retry={review.retry}/>}
          {!review.loading && review.data.length === 0 && <p className="v2-muted">No unresolved source-key decisions are queued. The imported identities remain provisional and are not represented as verified global identities.</p>}
        </>}
      </section>
      <div className="dashboard-grid"><section className="panel chart-panel"><div className="eyebrow">COMPETITIONS</div><h3>Covered player records</h3>{coverage.data.competitions.map(item => <div className="quality-row" key={item.id}><span>{item.name} · {number(item.players)} players</span><b>{number(item.records)} records</b></div>)}</section><section className="panel chart-panel"><div className="eyebrow">SEASONS</div><h3>Source coverage</h3>{coverage.data.seasons.map(item => <div className="quality-row" key={item.id}><span>{item.label} · {number(item.players)} players</span><b>{number(item.records)} records</b></div>)}</section></div>
      <section className="v2-section"><div className="section-head"><div><div className="eyebrow">METRIC AVAILABILITY</div><h2>Fields by observed coverage</h2></div></div><div className="panel table-panel"><div className="table-scroll"><table><caption className="sr-only">Count of available observations for each supported metric</caption><thead><tr><th scope="col">METRIC</th><th scope="col">STATUS</th><th scope="col">OBSERVED</th><th scope="col">TOTAL RECORDS</th><th scope="col">COVERAGE</th></tr></thead><tbody>{coverage.data.metrics.map(item => <tr key={item.metric}><td>{metricLabel[item.metric] ?? item.metric}</td><td><span className={`v2-status ${item.status}`}>{item.status}</span></td><td>{number(item.available_records)}</td><td>{number(item.total_records)}</td><td>{item.total_records ? `${((item.available_records / item.total_records) * 100).toFixed(1)}%` : '—'}</td></tr>)}</tbody></table></div></div></section>
      <section className="v2-section"><div className="section-head"><div><div className="eyebrow">PANDAS QUALITY PROFILE</div><h2>Record completeness and validation checks</h2></div></div>
        {quality.error && <ErrorState message={quality.error} retry={quality.retry}/>}
        {quality.loading ? <Loading label="Summarizing current source record quality"/> : <>
          <div className="metrics-grid compact"><div className="metric-card"><div className="metric-top">COMPLETENESS</div><div className="metric-value">{number(quality.data.completeness_percent, 2)}%</div></div><div className="metric-card"><div className="metric-top">MISSING CELLS</div><div className="metric-value">{number(quality.data.missing_cells)}</div></div><div className="metric-card"><div className="metric-top">DUPLICATE SOURCE KEYS</div><div className="metric-value">{number(quality.data.duplicate_source_key_records)}</div></div><div className="metric-card"><div className="metric-top">POTENTIAL NEGATIVE COUNTS</div><div className="metric-value">{number(quality.data.potential_invalid_values.negative_count_metric_cells)}</div></div></div>
          <div className="v2-chart-actions"><button className="btn-outline" onClick={() => void generateQualityImage()} disabled={qualityImageLoading}>{qualityImageLoading ? 'Generating…' : 'Generate missingness chart'}</button>{qualityImageBlob && <button className="btn-outline" onClick={() => saveBlob(qualityImageBlob, 'pitchiq_v2_missingness.png')}><Download size={14}/> Export PNG</button>}</div>
          {qualityImageError && <div className="notice" role="alert">{qualityImageError}</div>}
          {qualityImageUrl && <div className="v2-generated-chart"><img src={qualityImageUrl} alt="Seaborn chart of the percentage of missing records in each current-release column"/></div>}
          <div className="panel table-panel"><div className="table-scroll"><table><caption className="sr-only">Per-column missing values, declared type, and observed unique values</caption><thead><tr><th scope="col">COLUMN</th><th scope="col">TYPE</th><th scope="col">MISSING</th><th scope="col">MISSING %</th><th scope="col">UNIQUE OBSERVED</th></tr></thead><tbody>{quality.data.columns.map(item => <tr key={item.column}><th scope="row">{item.column}</th><td>{item.declared_type || item.dtype}</td><td>{number(item.missing_count)}</td><td>{number(item.missing_percent, 2)}%</td><td>{number(item.unique_values)}</td></tr>)}</tbody></table></div></div>
          <p className="v2-provenance">{quality.data.methodology} Duplicate content candidates: {number(quality.data.duplicate_content_records)} rows. The source schema also constrains negative minutes and out-of-range ages; current observed violations are {number(quality.data.potential_invalid_values.negative_minutes_records)} and {number(quality.data.potential_invalid_values.age_outside_0_100_records)}.</p>
        </>}
      </section>
      <Methodology>The dataset contains source player records, not an authoritative global player directory. Generated local identities remain provisional. Missing statistical fields remain null and unavailable metrics are excluded. Dataset usage rights are unverified.</Methodology>
    </>}
  </>;
}

export function ShootingLeaderboardsMetric({ definition }: { definition: MetricDefinition }) { return <span>{definition.display_name}</span>; }
