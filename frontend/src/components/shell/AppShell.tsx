import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import { CLASSIC_NAV_GROUP, DIRECTORY_NAV_GROUP, NAV_GROUPS, type NavigationGroup, resolveNavigation } from './navConfig';

type ApiState = 'checking' | 'online' | 'offline';

type AppShellProps = {
  children: ReactNode;
  pathname: string;
  apiState: ApiState;
  datasetLabel: string;
  version: string;
};

function NavigationGroupView({ group, pathname, onNavigate }: { group: NavigationGroup; pathname: string; onNavigate: () => void }) {
  return (
    <section className="pq-nav__group" aria-label={group.label}>
      <h2 className="pq-nav__label">{group.label}</h2>
      {group.items.map(({ id, label, to, icon: Icon, isActive }) => {
        const active = isActive(pathname);
        return (
          <Link
            key={id}
            to={to}
            className={`pq-nav__item${active ? ' is-active' : ''}`}
            aria-current={active ? 'page' : undefined}
            onClick={onNavigate}
          >
            <Icon aria-hidden="true" strokeWidth={1.75} />
            <span>{label}</span>
          </Link>
        );
      })}
    </section>
  );
}

export function AppShell({ children, pathname, apiState, datasetLabel, version }: AppShellProps) {
  const [open, setOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const sidebar = useRef<HTMLElement>(null);
  const current = resolveNavigation(pathname);

  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        requestAnimationFrame(() => menuButton.current?.focus());
      }
    };
    window.addEventListener('keydown', onKeyDown);
    requestAnimationFrame(() => sidebar.current?.querySelector<HTMLAnchorElement>('a')?.focus());
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open]);

  const closeDrawer = () => {
    if (!open) return;
    setOpen(false);
    if (window.matchMedia('(max-width: 900px)').matches) requestAnimationFrame(() => menuButton.current?.focus());
  };

  return (
    <div className="pq-app" data-nav-open={open ? 'true' : 'false'}>
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <aside className="pq-sidebar" id="pq-sidebar" ref={sidebar} aria-label="Primary navigation">
        <Link className="pq-brand" to="/" aria-label="PITCHIQ home" onClick={() => setOpen(false)}>
          <span className="pq-brand__mark" aria-hidden="true">P.</span>
          <span>
            <span className="pq-brand__word">PITCH<b>IQ</b></span>
            <span className="pq-brand__sub">Football intelligence</span>
          </span>
        </Link>
        <nav className="pq-nav" aria-label="Main navigation">
          {NAV_GROUPS.map(group => <NavigationGroupView key={group.label} group={group} pathname={pathname} onNavigate={closeDrawer} />)}
          <details className="pq-nav__classic pq-nav__directories" open={DIRECTORY_NAV_GROUP.items.some(item => item.isActive(pathname))}>
            <summary className="pq-nav__label">{DIRECTORY_NAV_GROUP.label}<span aria-hidden="true">⌄</span></summary>
            <NavigationGroupView group={{ ...DIRECTORY_NAV_GROUP, label: 'Dataset directories' }} pathname={pathname} onNavigate={closeDrawer} />
          </details>
          <details className="pq-nav__classic" open={CLASSIC_NAV_GROUP.items.some(item => item.isActive(pathname))}>
            <summary className="pq-nav__label">{CLASSIC_NAV_GROUP.label}<span aria-hidden="true">⌄</span></summary>
            <NavigationGroupView group={{ ...CLASSIC_NAV_GROUP, label: 'Original CSV-backed pages' }} pathname={pathname} onNavigate={closeDrawer} />
          </details>
        </nav>
        <div className="pq-sidebar__foot">
          <div className="pq-dataset"><span className="pq-dot" aria-hidden="true" />{datasetLabel}</div>
          <div className="pq-version">{version}</div>
        </div>
      </aside>

      {open && <button type="button" className="pq-scrim" aria-label="Close navigation" onClick={closeDrawer} />}

      <div className="pq-main">
        <header className="pq-topbar">
          <button
            ref={menuButton}
            type="button"
            className="pq-menu-btn"
            aria-label={open ? 'Close navigation' : 'Open navigation'}
            aria-expanded={open}
            aria-controls="pq-sidebar"
            onClick={() => setOpen(value => !value)}
          >
            {open ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
          </button>
          <nav className="pq-crumbs" aria-label="Breadcrumb">
            <span>PITCHIQ</span><span aria-hidden="true">/</span><span aria-current="page">{current.label}</span>
          </nav>
          <div className="pq-topbar__right">
            <div className="pq-api" data-state={apiState} role="status" aria-live="polite">
              <span className="pq-dot" aria-hidden="true" />
              <span>{apiState === 'checking' ? 'Checking API' : apiState === 'online' ? 'API connected' : 'API offline'}</span>
            </div>
            <span className="pq-topbar__rule" aria-hidden="true" />
            <span className="pq-avatar" aria-label="PITCHIQ">IQ</span>
          </div>
        </header>

        <main className="pq-content" id="main-content" tabIndex={-1}>
          {children}
          <footer className="pq-footer"><span>PITCHIQ <b aria-hidden="true">●</b> FOOTBALL ANALYTICS</span><span>POWERED BY PYTHON · PANDAS · NUMPY</span></footer>
        </main>
      </div>
    </div>
  );
}
