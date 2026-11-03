import { ArrowUpRight, BarChart3, TrendingUp, Trophy, Users } from 'lucide-react';
import { NavLink } from 'react-router-dom';

const FEATURE_CARDS = [
  { id: 'explore', title: 'Explore players', text: 'Search and discover players across competitions', to: '/database', icon: Users },
  { id: 'compare', title: 'Compare players', text: 'Side-by-side performance analysis', to: '/database/compare', icon: BarChart3 },
  { id: 'patterns', title: 'Analyse patterns', text: 'Find trends and relationships across metrics', to: '/database/analytics/correlation', icon: TrendingUp },
  { id: 'competitions', title: 'Track competitions', text: 'Analyse performance across leagues and tournaments', to: '/database/competitions', icon: Trophy },
];

export function FeatureCards() {
  return (
    <nav className="pq-cards" aria-label="Explore PITCHIQ">
      {FEATURE_CARDS.map(({ id, title, text, to, icon: Icon }) => (
        <NavLink className="pq-card" to={to} key={id}>
          <Icon className="pq-card__icon" aria-hidden="true"/>
          <ArrowUpRight className="pq-card__go" aria-hidden="true"/>
          <span className="pq-card__title">{title}</span>
          <span className="pq-card__text">{text}</span>
        </NavLink>
      ))}
    </nav>
  );
}
