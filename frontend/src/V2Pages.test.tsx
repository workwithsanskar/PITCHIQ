import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CompareV2Page, DataLabPage, DatabasePage } from './V2Pages';

const mocks = vi.hoisted(() => ({
  coverage: vi.fn(), positions: vi.fn(), metrics: vi.fn(), descriptive: vi.fn(), dataLab: vi.fn(), players: vi.fn(), compare: vi.fn(),
  exportPlayers: vi.fn(), exportComparison: vi.fn(), exportDataLab: vi.fn(), visualization: vi.fn(), outliers: vi.fn(), exportDescriptive: vi.fn(), exportOutliers: vi.fn(),
}));

vi.mock('./v2Api', () => ({ v2Api: mocks }));

const summary = {
  metrics: ['goals_per90', 'assists_per90'], record_count: 2, group_by: 'competition', groups: [], methodology: 'Pandas and NumPy summary fixture.',
  summary: [
    { metric: 'goals_per90', count: 2, mean: .5, median: .5, standard_deviation: .14, variance: .02, minimum: .4, q1: .45, q2: .5, q3: .55, interquartile_range: .1, maximum: .6 },
    { metric: 'assists_per90', count: 2, mean: .25, median: .25, standard_deviation: .07, variance: .005, minimum: .2, q1: .225, q2: .25, q3: .275, interquartile_range: .05, maximum: .3 },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.coverage.mockResolvedValue({ source_context: { release_name: 'Current release', rights_status: 'unverified' }, player_count: 2, record_count: 2, clubs: [{ id: 'c1', name: 'North FC', players: 2, records: 2 }], competitions: [{ id: 'comp1', name: 'League One', players: 2, records: 2 }], seasons: [{ id: '2025', label: '2025–26', players: 2, records: 2 }], metrics: [] });
  mocks.positions.mockResolvedValue({ items: [{ listed_position: 'DF', players: 1, records: 1 }, { listed_position: 'FW', players: 1, records: 1 }, { listed_position: 'MF', players: 1, records: 1 }], methodology: '' });
  mocks.metrics.mockResolvedValue({ items: [{ metric_key: 'goals_per90', display_name: 'Goals / 90' }, { metric_key: 'assists_per90', display_name: 'Assists / 90' }, { metric_key: 'goals', display_name: 'Goals' }], available_metrics: ['goals_per90', 'assists_per90', 'goals'], unsupported: ['xg'] });
  mocks.descriptive.mockResolvedValue(summary);
  mocks.dataLab.mockResolvedValue({ visualization: 'table', metrics: ['goals_per90', 'assists_per90'], total: 2, summary: summary.summary, units: ['goals/90', 'assists/90'], source_context: { release_name: 'Current release', rights_status: 'unverified' }, items: [{ player_id: 'p1', player: 'Ari Striker', club: 'North FC', competition: 'League One', season: '2025–26', values: { goals_per90: .6, assists_per90: .2 } }] });
  mocks.exportDataLab.mockResolvedValue(new Blob(['csv']));
  mocks.visualization.mockResolvedValue(new Blob(['png'], { type: 'image/png' }));
  mocks.outliers.mockResolvedValue({ metric: 'goals', n: 0, q1: null, q3: null, iqr: null, lower_bound: null, upper_bound: null, outlier_count: 0, items: [] });
  mocks.exportDescriptive.mockResolvedValue(new Blob(['summary']));
  mocks.exportOutliers.mockResolvedValue(new Blob(['outliers']));
  mocks.exportPlayers.mockReturnValue('/api/v2/exports/players');
  mocks.exportComparison.mockResolvedValue(new Blob(['comparison']));
  mocks.players.mockImplementation(async (filters: Record<string, string | number | undefined>) => {
    const items = explorerPlayers.filter(player => {
      const term = String(filters.search ?? '').toLowerCase().trim();
      return (!term || `${player.canonical_name} ${player.alias} ${player.club}`.toLowerCase().includes(term))
        && (!filters.position || player.primary_position === filters.position)
        && player.minutes >= Number(filters.minimum_minutes ?? 0);
    }).sort((left, right) => {
      const key = String(filters.sort_by ?? 'name');
      const order = filters.order === 'desc' ? -1 : 1;
      const a = left[key as keyof typeof left]; const b = right[key as keyof typeof right];
      return (typeof a === 'number' && typeof b === 'number' ? a - b : String(a ?? '').localeCompare(String(b ?? ''))) * order;
    });
    const offset = Number(filters.offset ?? 0); const limit = Number(filters.limit ?? 50);
    return { items: items.slice(offset, offset + limit), meta: { total: items.length, limit, offset }, source_context: {} };
  });
  URL.createObjectURL = vi.fn(() => 'blob:pitchiq-test');
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const renderPage = () => render(<MemoryRouter><DataLabPage/></MemoryRouter>);

const explorerPlayers = [
  { id: 'p-aaron', canonical_name: 'Aaron Anselmino', alias: 'Aaron A.', club: 'North FC', nationality: null, primary_position: 'DF', identity_status: 'provisional', record_count: 1, club_count: 1, competition_count: 1, seasons: ['2025–26'], appearances: 10, starts: 6, minutes: 620, goals: 2, assists: 1, contributions_per90: 0.44 },
  { id: 'p-jake', canonical_name: 'Jake Aaron', alias: 'J. Aaron', club: 'South FC', nationality: null, primary_position: 'FW', identity_status: 'provisional', record_count: 1, club_count: 1, competition_count: 1, seasons: ['2025–26'], appearances: 12, starts: 9, minutes: 810, goals: 4, assists: 0, contributions_per90: 0.44 },
];

describe('PITCHIQ v2 Data Lab', () => {
  it('runs a filtered statistical query and displays descriptive and table results', async () => {
    renderPage();
    await screen.findByRole('heading', { name: 'Ask the data a question.' });
    fireEvent.change(screen.getByLabelText('Visualization'), { target: { value: 'table' } });
    fireEvent.change(screen.getByLabelText('Competition'), { target: { value: 'comp1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }));
    expect(await screen.findByText('Ari Striker')).toBeInTheDocument();
    expect(await screen.findByText('FILTERED RECORD SUMMARY')).toBeInTheDocument();
    expect(mocks.descriptive).toHaveBeenCalledWith(expect.objectContaining({ metrics: ['goals_per90', 'assists_per90'], competition_id: 'comp1' }), expect.any(AbortSignal));
    expect(mocks.dataLab).toHaveBeenCalledWith(expect.objectContaining({ visualization: 'table', competition_id: 'comp1' }), expect.any(AbortSignal));
  });

  it('exports the filtered Data Lab result as CSV', async () => {
    renderPage();
    await screen.findByRole('heading', { name: 'Ask the data a question.' });
    fireEvent.change(screen.getByLabelText('Visualization'), { target: { value: 'table' } });
    fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }));
    await screen.findByText('Ari Striker');
    fireEvent.click(screen.getByRole('button', { name: /export csv/i }));
    await waitFor(() => expect(mocks.exportDataLab).toHaveBeenCalledWith(expect.objectContaining({ visualization: 'table', metrics: ['goals_per90', 'assists_per90'] })));
  });

  it('shows an API error with a retry action', async () => {
    mocks.descriptive.mockRejectedValueOnce(new Error('Analytics service unavailable'));
    renderPage();
    await screen.findByRole('heading', { name: 'Ask the data a question.' });
    fireEvent.change(screen.getByLabelText('Visualization'), { target: { value: 'table' } });
    fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Analytics service unavailable');
    fireEvent.click(screen.getByRole('button', { name: 'Retry analysis' }));
    expect(await screen.findByText('Ari Striker')).toBeInTheDocument();
  });
});

describe('PITCHIQ v2 Player Explorer search', () => {
  it('debounces player search and applies position, minutes, and sorting in the same request', async () => {
    render(<MemoryRouter><DatabasePage/></MemoryRouter>);
    const search = await screen.findByLabelText('Search player, alias, or club');
    fireEvent.change(screen.getByLabelText('Position'), { target: { value: 'DF' } });
    fireEvent.change(search, { target: { value: 'Aaron' } });

    await waitFor(() => expect(mocks.players).toHaveBeenLastCalledWith(
      expect.objectContaining({ search: 'Aaron', position: 'DF', minimum_minutes: 0, sort_by: 'name', order: 'asc', offset: 0 }),
      expect.any(AbortSignal),
    ));
    expect(await screen.findByRole('link', { name: 'Aaron Anselmino' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Jake Aaron' })).not.toBeInTheDocument();
    expect(screen.getByText('1 canonical players')).toBeInTheDocument();
  });

  it('shows an empty search state, keeps the input mounted, and restores results when cleared', async () => {
    render(<MemoryRouter><DatabasePage/></MemoryRouter>);
    const search = await screen.findByLabelText('Search player, alias, or club');
    search.focus();
    fireEvent.change(search, { target: { value: 'No such player' } });
    expect(search).toHaveFocus();
    expect(await screen.findByText('No players match this scope. Clear or widen the filters.')).toBeInTheDocument();
    expect(search).toHaveFocus();

    fireEvent.click(screen.getByRole('button', { name: 'Clear player search' }));
    expect(await screen.findByRole('link', { name: 'Aaron Anselmino' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Jake Aaron' })).toBeInTheDocument();
    expect(mocks.players).toHaveBeenLastCalledWith(expect.objectContaining({ search: undefined, offset: 0 }), expect.any(AbortSignal));
  });

  it('shows a retryable API error instead of stale player rows', async () => {
    mocks.players.mockRejectedValueOnce(new Error('Player search unavailable'));
    render(<MemoryRouter><DatabasePage/></MemoryRouter>);
    expect(await screen.findByRole('alert')).toHaveTextContent('Player search unavailable');
    expect(screen.queryByRole('link', { name: 'Aaron Anselmino' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByRole('link', { name: 'Aaron Anselmino' })).toBeInTheDocument();
  });
});

describe('PITCHIQ v2 Player Comparison', () => {
  const record = (club: string, competition: string) => ({ club, competition, season: '2025–26' });
  const compared = [
    { id: 'p1', canonical_name: 'Aaron Anselmino', primary_position: 'DF', record_count: 1, minutes: 620, appearances: 10, starts: 6, goals: 2, assists: 1, goals_per90: 0.29, assists_per90: 0.15, records: [record('North FC', 'League One')] },
    { id: 'p2', canonical_name: 'Kai Defender', primary_position: 'DF', record_count: 1, minutes: 500, appearances: 8, starts: 5, goals: 0, assists: null, goals_per90: 0, assists_per90: null, records: [record('South FC', 'League Two')] },
  ];

  it('shows player context, zero and unavailable values, grouped stats, and CSV export', async () => {
    mocks.compare.mockResolvedValue({ items: compared, scope: {}, methodology: 'Source-record aggregates.', source_context: {} });
    render(<MemoryRouter initialEntries={['/database/compare?player=p1&player=p2']}><CompareV2Page/></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button', { name: 'Compare players' }));

    expect(await screen.findByRole('region', { name: 'Player comparison results' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Aaron Anselmino' })).toBeInTheDocument();
    expect(screen.getByText('North FC')).toBeInTheDocument();
    expect(screen.getAllByText('League One').length).toBeGreaterThan(0);
    expect(screen.getByText('Compare the covered numbers.')).toBeInTheDocument();
    expect(screen.getAllByRole('meter', { name: 'Kai Defender: 0' }).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0);
    expect(screen.getByText(/Source-record aggregates\./)).toBeInTheDocument();
    expect(screen.queryByText('Passing')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Export comparison' }));
    await waitFor(() => expect(mocks.exportComparison).toHaveBeenCalledWith({ player_ids: ['p1', 'p2'], minimum_minutes: 0 }));
  });

  it('renders four selected players without treating mixed positions as a ranking', async () => {
    const four = ['One', 'Two', 'Three', 'Four'].map((name, index) => ({
      id: `p${index + 1}`, canonical_name: `Player ${name}`, primary_position: index === 3 ? 'GK' : 'DF',
      record_count: 1, minutes: 90 + index, appearances: 1, starts: 1, goals: index, assists: 0,
      goals_per90: index, assists_per90: 0, records: [record('Club FC', 'League One')],
    }));
    mocks.compare.mockResolvedValue({ items: four, scope: {}, methodology: 'Record totals.', source_context: {} });
    render(<MemoryRouter initialEntries={['/database/compare?player=p1&player=p2&player=p3&player=p4']}><CompareV2Page/></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button', { name: 'Compare players' }));

    expect(await screen.findByRole('heading', { name: 'Player Four' })).toBeInTheDocument();
    expect(screen.getByText(/Positions differ or are unavailable/)).toBeInTheDocument();
    expect(mocks.compare).toHaveBeenCalledWith({ player_ids: ['p1', 'p2', 'p3', 'p4'], minimum_minutes: 0 }, expect.any(AbortSignal));
    expect(screen.getByRole('button', { name: 'Export comparison' })).toBeInTheDocument();
  });
});
