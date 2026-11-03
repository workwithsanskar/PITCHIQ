import {
  Activity,
  BarChart3,
  Database,
  FlaskConical,
  Goal,
  ShieldCheck,
  Target,
  Trophy,
  Users,
  type LucideIcon,
} from 'lucide-react';

export type NavigationItem = {
  id: string;
  label: string;
  to: string;
  icon: LucideIcon;
  isActive: (pathname: string) => boolean;
};

export type NavigationGroup = { label: string; items: NavigationItem[] };

const exact = (route: string) => (pathname: string) => pathname === route;
const routeOrChild = (route: string) => (pathname: string) => pathname === route || pathname.startsWith(`${route}/`);

export const NAV_GROUPS: NavigationGroup[] = [
  { label: 'OVERVIEW', items: [{ id: 'overview', label: 'Overview', to: '/', icon: Activity, isActive: exact('/') }] },
  {
    label: 'PLAYERS',
    items: [
      { id: 'player-explorer', label: 'Player explorer', to: '/database', icon: Users, isActive: path => path === '/database' || path.startsWith('/database/player/') },
      { id: 'player-comparison', label: 'Player comparison', to: '/database/compare', icon: BarChart3, isActive: exact('/database/compare') },
      { id: 'leaderboards', label: 'Leaderboards', to: '/database/leaderboards', icon: Goal, isActive: exact('/database/leaderboards') },
    ],
  },
  {
    label: 'ANALYTICS',
    items: [
      { id: 'shooting', label: 'Shooting', to: '/database/shooting', icon: Target, isActive: exact('/database/shooting') },
      { id: 'descriptive-statistics', label: 'Descriptive statistics', to: '/database/analytics/descriptive', icon: BarChart3, isActive: exact('/database/analytics/descriptive') },
      { id: 'correlation-analysis', label: 'Correlation analysis', to: '/database/analytics/correlation', icon: Activity, isActive: exact('/database/analytics/correlation') },
      { id: 'distributions-outliers', label: 'Distributions & outliers', to: '/database/analytics/distributions', icon: BarChart3, isActive: exact('/database/analytics/distributions') },
      { id: 'competitions', label: 'Competitions', to: '/database/competitions', icon: Trophy, isActive: routeOrChild('/database/competitions') },
      { id: 'data-lab-v2', label: 'Data Lab', to: '/database/data-lab', icon: FlaskConical, isActive: exact('/database/data-lab') },
    ],
  },
  {
    label: 'DATA',
    items: [
      { id: 'quality-coverage', label: 'Quality & coverage', to: '/database/coverage', icon: ShieldCheck, isActive: exact('/database/coverage') },
    ],
  },
];

export const DIRECTORY_NAV_GROUP: NavigationGroup = {
  label: 'DIRECTORIES',
  items: [
    { id: 'club-directory', label: 'Club directory', to: '/database/clubs', icon: Database, isActive: routeOrChild('/database/clubs') },
    { id: 'season-directory', label: 'Season directory', to: '/database/seasons', icon: Database, isActive: routeOrChild('/database/seasons') },
  ],
};

export const CLASSIC_NAV_GROUP: NavigationGroup = {
  label: 'CLASSIC WORKSPACE',
  items: [
    { id: 'player-discovery', label: 'Player discovery', to: '/players', icon: Users, isActive: path => path === '/players' || /^\/players\/\d+$/.test(path) },
    { id: 'teams', label: 'Teams', to: '/teams', icon: Goal, isActive: exact('/teams') },
    { id: 'comparison', label: 'Comparison', to: '/compare', icon: BarChart3, isActive: exact('/compare') },
    { id: 'data-lab-classic', label: 'Data Lab', to: '/data-lab', icon: FlaskConical, isActive: exact('/data-lab') },
  ],
};

export const ALL_NAV_ITEMS = [...NAV_GROUPS.flatMap(group => group.items), ...DIRECTORY_NAV_GROUP.items, ...CLASSIC_NAV_GROUP.items];

export function resolveNavigation(pathname: string) {
  return ALL_NAV_ITEMS.find(item => item.isActive(pathname)) ?? {
    id: 'overview',
    label: 'PITCHIQ',
    to: '/',
    icon: Activity,
    isActive: exact('/'),
  };
}
