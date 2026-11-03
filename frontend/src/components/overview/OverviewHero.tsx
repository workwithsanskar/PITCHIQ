import type { ReactNode } from 'react';
import { ArrowUpRight, BarChart3 } from 'lucide-react';
import { NavLink } from 'react-router-dom';

function bundle(count: number, start: number[], end: number[]) {
  return Array.from({ length: count }, (_, index) => {
    const amount = count === 1 ? 0 : index / (count - 1);
    const point = start.map((value, part) => value + (end[part] - value) * amount);
    return `M${point[0]} ${point[1]} C${point[2]} ${point[3]}, ${point[4]} ${point[5]}, ${point[6]} ${point[7]}`;
  });
}

const ARCS_LEFT = bundle(9, [760, -20, 640, 140, 700, 330, 420, 600], [840, -20, 700, 170, 790, 380, 560, 620]);
const ARCS_RIGHT = bundle(16, [1200, 330, 1040, 400, 900, 470, 640, 600], [1200, 150, 1060, 300, 960, 400, 800, 600]);

function HeroArcs() {
  return (
    <svg className="pq-hero__arcs" viewBox="0 0 1200 560" preserveAspectRatio="xMaxYMid slice" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="pq-arc-a" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#b9f032" stopOpacity="0.75"/><stop offset="1" stopColor="#b9f032" stopOpacity="0"/></linearGradient>
        <linearGradient id="pq-arc-b" x1="1" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#b9f032" stopOpacity="0.6"/><stop offset="1" stopColor="#b9f032" stopOpacity="0"/></linearGradient>
      </defs>
      <g fill="none" strokeWidth="1">
        {ARCS_LEFT.map((path, index) => <path key={`left-${index}`} d={path} stroke="url(#pq-arc-a)" opacity={0.5 + (index % 3) * 0.25}/>)}
        {ARCS_RIGHT.map((path, index) => <path key={`right-${index}`} d={path} stroke="url(#pq-arc-b)" opacity={0.4 + (index % 4) * 0.16}/>)}
      </g>
    </svg>
  );
}

export function OverviewHero({ season, ball }: { season: string; ball: ReactNode }) {
  return (
    <section className="pq-hero" aria-labelledby="pq-hero-title">
      <HeroArcs />
      <div className="pq-hero__copy">
        <p className="pq-eyebrow hero-reveal">The numbers behind the game</p>
        <h1 id="pq-hero-title" className="pq-hero__title hero-reveal">
          <span className="pq-line">Read the game.</span>
          <span className="pq-line pq-lime">Own the <span className="pq-outline">data.</span></span>
        </h1>
        <p className="pq-hero__lede hero-reveal">A deeper look at the players, performances and patterns shaping the {season} football season.</p>
        <div className="pq-hero__actions hero-reveal">
          <NavLink to="/database" className="pq-btn pq-btn--primary">Explore players <ArrowUpRight aria-hidden="true"/></NavLink>
          <NavLink to="/database/data-lab" className="pq-btn pq-btn--ghost"><BarChart3 aria-hidden="true"/> Explore the data</NavLink>
        </div>
        <p className="pq-status hero-reveal"><span className="pq-dot" aria-hidden="true"/>Live from the dataset<i aria-hidden="true"/>{season}</p>
      </div>
      <div className="pq-hero__stage" aria-hidden="true">
        <span className="pq-hero__glow"/><span className="pq-hero__floor"/><span className="pq-hero__rim"/>
        <div className="pq-hero__ball">{ball}</div>
      </div>
      <p className="pq-hero__counter" aria-hidden="true">01 <span>—</span> 06</p>
      <p className="pq-hero__tagline" aria-hidden="true"><span>01 / 03</span>Performance is everything</p>
    </section>
  );
}
