import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import App from './App';
import type { PlayerQuery } from './api';
import type { Player } from './types';

const sample: Player[] = [
  { Rk: 1, Player: 'Ari Striker', Nation: 'ENG', Pos: 'FW', Squad: 'North FC', Comp: 'eng Premier League', Age: 24, Min: 1200, Gls: 12, Ast: 4, 'G+A': 16, Sh: 30, SoT: 14, 'SoT%': 46.7, shot_accuracy: 46.7, goals_per90: .9, assists_per90: .3, contributions_per90: 1.2 },
  { Rk: 2, Player: 'Bea Midfield', Nation: 'ESP', Pos: 'MF', Squad: 'South FC', Comp: 'es La Liga', Age: 26, Min: 900, Gls: 5, Ast: 8, 'G+A': 13, Sh: 20, SoT: 9, 'SoT%': 45, shot_accuracy: 45, goals_per90: .5, assists_per90: .8, contributions_per90: 1.3 },
];
const mocks = vi.hoisted(() => ({ playersRequest: vi.fn(), compareRequest: vi.fn(), overviewRequest: vi.fn(), teamsRequest: vi.fn() }));

vi.mock('./api', () => ({ api: {
  health: vi.fn(async () => ({ status: 'healthy', rows: 2, columns: 53 })),
  overview: (...args: [AbortSignal?, { competition?: string; squad?: string; position?: string; min_minutes?: number }?]) => mocks.overviewRequest(...args),
  players: (...args: [PlayerQuery?, AbortSignal?]) => mocks.playersRequest(...args),
  player: vi.fn(async (rank: number) => sample.find(p => p.Rk === rank)),
  playerOptions: vi.fn(async () => sample.map(({ Rk, Player, Squad, Pos, Comp }) => ({ Rk, Player, Squad, Pos, Comp }))),
  teams: (...args: [AbortSignal?, { competition?: string; squad?: string; position?: string; min_minutes?: number }?]) => mocks.teamsRequest(...args),
  filters: vi.fn(async () => ({ squads: ['North FC', 'South FC'], competitions: ['eng Premier League', 'es La Liga'], positions: ['FW', 'MF'] })),
  positions: vi.fn(async () => []),
  correlation: vi.fn(async () => ({ labels: [], matrix: [], method: '', note: '' })),
  quality: vi.fn(async () => ({ rows: 2, columns: 53, missing_cells: 0, duplicate_rows: 0, duplicate_rk: 0, missing_names: 0, missing_squads: 0, missing_by_column: {}, zero_minute_records: 0, dataset: 'fixture.csv' })),
  compare: (...args: [number[], AbortSignal?]) => mocks.compareRequest(...args),
  leaderboard: vi.fn(async () => ({ metric: 'goals_per90', minimum_minutes: 450, methodology: '', items: sample })),
  competitions: vi.fn(async () => ({ methodology: '', competitions: [], positions: [], top_scorers: [] })),
} }));

beforeEach(() => {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn().mockImplementation((media: string) => ({
      matches: false,
      media,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
  mocks.playersRequest.mockReset();
  mocks.compareRequest.mockReset();
  mocks.overviewRequest.mockReset();
  mocks.teamsRequest.mockReset();
  mocks.overviewRequest.mockResolvedValue({ players: 2, records: 2, teams: 2, competitions: 2, goals: 17, assists: 12, minutes: 2100, shots: 50, avg_age: 25, season: '2025 / 26' });
  mocks.teamsRequest.mockResolvedValue([]);
  mocks.playersRequest.mockImplementation(async (query: PlayerQuery = {}) => {
    const matches = sample.filter(p => (!query.search || `${p.Player} ${p.Squad}`.toLowerCase().includes(query.search.toLowerCase())) && (!query.position || p.Pos === query.position) && (!query.squad || p.Squad === query.squad) && (!query.competition || p.Comp === query.competition) && (p.Min ?? 0) >= (query.min_minutes ?? 0));
    return { total: matches.length, items: matches };
  });
  mocks.compareRequest.mockImplementation(async (ids: number[]) => sample.filter(p => ids.includes(p.Rk)));
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });
const renderAt = (path: string) => render(<MemoryRouter initialEntries={[path]}><App/></MemoryRouter>);

describe('PITCHIQ data screens', () => {
  it('provides skip navigation and grouped primary destinations', () => {
    renderAt('/players');
    expect(screen.getByRole('link', { name: 'Skip to main content' })).toHaveAttribute('href', '#main-content');
    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'PLAYERS' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Player comparison' })).toHaveAttribute('href', '/database/compare');
    expect(screen.getByRole('link', { name: 'Descriptive statistics' })).toHaveAttribute('href', '/database/analytics/descriptive');
    expect(screen.getByRole('link', { name: 'Player discovery' })).toBeInTheDocument();
  });

  it('filters the overview KPIs, team chart and top players using the same scope', async () => {
    const user = userEvent.setup(); renderAt('/');
    await screen.findByRole('heading', { name: /by numbers/i });
    await user.selectOptions(screen.getByRole('combobox', { name: 'Overview competition' }), 'eng Premier League');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Overview minimum minutes' }), '900');
    await waitFor(() => expect(mocks.overviewRequest).toHaveBeenLastCalledWith(expect.any(AbortSignal), expect.objectContaining({ competition: 'eng Premier League', min_minutes: 900 })));
    await waitFor(() => expect(mocks.teamsRequest).toHaveBeenLastCalledWith(expect.any(AbortSignal), expect.objectContaining({ competition: 'eng Premier League', min_minutes: 900 })));
    await waitFor(() => expect(mocks.playersRequest).toHaveBeenLastCalledWith(expect.objectContaining({ competition: 'eng Premier League', min_minutes: 900, limit: 6 }), expect.any(AbortSignal)));
    await user.click(screen.getByRole('button', { name: 'Clear filters' }));
    await waitFor(() => expect(mocks.overviewRequest).toHaveBeenLastCalledWith(expect.any(AbortSignal), expect.objectContaining({ competition: undefined, min_minutes: 0 })));
  });

  it('loads and filters players, exposes a result count, and exports the active filters', async () => {
    const user = userEvent.setup(); renderAt('/players');
    expect((await screen.findAllByText('Ari Striker')).length).toBeGreaterThan(0);
    const search = screen.getByLabelText('Search player or club');
    await user.type(search, 'North');
    expect(await screen.findByText('1 MATCHING RECORDS')).toBeInTheDocument();
    const exportLink = screen.getByRole('link', { name: /export csv/i });
    expect(exportLink.getAttribute('href')).toContain('search=North');
    await user.click(screen.getByRole('button', { name: /clear filters/i }));
    expect(await screen.findByText('2 MATCHING RECORDS')).toBeInTheDocument();
  });

  it('supports navigation to the player comparison and selecting distinct players', async () => {
    const user = userEvent.setup(); renderAt('/players');
    await user.click(screen.getByRole('link', { name: 'Comparison' }));
    expect(await screen.findByRole('heading', { name: /four profiles/i })).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText('Choose player 1'), '1');
    await user.selectOptions(screen.getByLabelText('Choose player 2'), '2');
    await user.click(screen.getByRole('button', { name: /compare players/i }));
    await waitFor(() => expect(mocks.compareRequest).toHaveBeenCalledWith([1, 2]));
    expect((await screen.findAllByText('Ari Striker')).length).toBeGreaterThan(0);
  });

  it('keeps the full selected comparison record available on small screens and to assistive technology', async () => {
    const user = userEvent.setup(); renderAt('/compare');
    const firstSelect = await screen.findByRole('combobox', { name: 'Choose player 1' });
    for (let step = 0; step < 80 && document.activeElement !== firstSelect; step++) await user.tab();
    expect(document.activeElement).toBe(firstSelect);
    await user.selectOptions(firstSelect, '1');
    const fullIdentity = 'Ari Striker — North FC · eng Premier League (#1)';
    expect(screen.getByRole('combobox', { name: `Choose player 1: ${fullIdentity}` })).toHaveAttribute('title', fullIdentity);
    expect(screen.getByText(`Selected record: ${fullIdentity}`)).toBeInTheDocument();
    expect(firstSelect.querySelector('option[value="1"]')).toHaveTextContent(fullIdentity);
  });

  it('opens the dataset-backed player detail page from discovery', async () => {
    const user = userEvent.setup(); renderAt('/players');
    await user.click(await screen.findByRole('link', { name: 'Ari Striker' }));
    expect(await screen.findByRole('heading', { name: /performance profile/i })).toBeInTheDocument();
    expect(screen.getByText('North FC')).toBeInTheDocument();
    expect(screen.getByText('Shooting accuracy is shots on target divided by total shots. It is not goal conversion.')).toBeInTheDocument();
  });

  it('shows a useful empty state when the filters produce no players', async () => {
    const user = userEvent.setup(); renderAt('/players');
    const search = screen.getByLabelText('Search player or club');
    await user.type(search, 'No such player');
    expect(await screen.findByText(/no players match these filters/i)).toBeInTheDocument();
  });

  it('renders loading and API failure states, then retries successfully', async () => {
    const user = userEvent.setup();
    mocks.playersRequest.mockRejectedValueOnce(new Error('Temporary API issue'));
    renderAt('/players');
    expect(screen.getByText('Loading player results')).toBeInTheDocument();
    expect(await screen.findByText('Temporary API issue')).toBeInTheDocument();
    const retry = screen.getByRole('button', { name: 'Retry' });
    for (let step = 0; step < 80 && document.activeElement !== retry; step++) await user.tab();
    expect(document.activeElement).toBe(retry);
    await user.click(retry);
    expect((await screen.findAllByText('Ari Striker')).length).toBeGreaterThan(0);
  });

  it('passes the selected sort field to the API and keeps accessible control labels', async () => {
    const user = userEvent.setup(); renderAt('/players');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Sort players by' }), 'Ast');
    await waitFor(() => expect(mocks.playersRequest).toHaveBeenCalledWith(expect.objectContaining({ sort_by: 'Ast' }), expect.any(AbortSignal)));
    expect(screen.getByRole('table', { name: /filtered player statistics/i })).toBeInTheDocument();
  });
});
