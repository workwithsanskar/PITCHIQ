import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { PositionSummary, Team } from '../types';

const lime = 'var(--pq-series-1)';
const tooltipStyle = { background: 'var(--pq-surface-2)', border: '1px solid var(--pq-line-strong)', borderRadius: 10, color: 'var(--pq-text)' };

export function TopTeamsChart({ teams }: { teams: Team[] }) {
  return <ResponsiveContainer width="100%" height={270}><BarChart data={teams} margin={{ top: 12, right: 8, left: -22, bottom: 0 }}><CartesianGrid stroke="var(--pq-grid)" vertical={false}/><XAxis dataKey="team" tick={{ fill: 'var(--pq-text-muted)', fontSize: 10 }} axisLine={false} tickLine={false}/><YAxis tick={{ fill: 'var(--pq-text-muted)', fontSize: 10 }} axisLine={false} tickLine={false}/><Tooltip contentStyle={tooltipStyle}/><Bar dataKey="goals" fill={lime} radius={[5, 5, 0, 0]} maxBarSize={34}/></BarChart></ResponsiveContainer>;
}

export function TeamGoalsChart({ teams }: { teams: Team[] }) {
  return <ResponsiveContainer width="100%" height={390}><BarChart data={teams} layout="vertical" margin={{ left: 12, right: 20 }}><CartesianGrid stroke="var(--pq-grid)" horizontal={false}/><XAxis type="number" tick={{ fill: 'var(--pq-text-muted)', fontSize: 10 }} axisLine={false} tickLine={false}/><YAxis dataKey="team" type="category" width={120} tick={{ fill: 'var(--pq-text-2)', fontSize: 11 }} axisLine={false} tickLine={false}/><Tooltip contentStyle={tooltipStyle}/><Bar dataKey="goals" fill={lime} radius={[0, 5, 5, 0]} maxBarSize={18}/></BarChart></ResponsiveContainer>;
}

export function PositionPlayersChart({ positions }: { positions: PositionSummary[] }) {
  return <ResponsiveContainer width="100%" height={260}><BarChart data={positions} margin={{ left: -18, bottom: 0 }}><CartesianGrid stroke="var(--pq-grid)" vertical={false}/><XAxis dataKey="primary_position" tick={{ fill: 'var(--pq-text-muted)', fontSize: 11 }} axisLine={false} tickLine={false}/><YAxis tick={{ fill: 'var(--pq-text-muted)', fontSize: 10 }} axisLine={false} tickLine={false}/><Tooltip contentStyle={tooltipStyle}/><Bar dataKey="players" fill={lime} radius={[5, 5, 0, 0]}/></BarChart></ResponsiveContainer>;
}
