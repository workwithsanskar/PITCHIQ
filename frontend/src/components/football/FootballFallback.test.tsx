import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import FootballFallback from './FootballFallback';

describe('FootballFallback', () => {
  it('renders an accessible football from the shared panel geometry', () => {
    const { container } = render(<FootballFallback size={160} />);

    expect(screen.getByRole('img', { name: 'Football' }).tagName.toLowerCase()).toBe('svg');
    expect(container.querySelectorAll('polygon').length).toBeGreaterThan(0);
  });
});
