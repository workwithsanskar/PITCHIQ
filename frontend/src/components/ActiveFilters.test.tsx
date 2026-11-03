import { describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ActiveFilters } from './ActiveFilters';

describe('ActiveFilters', () => {
  it('names each removable filter for assistive technology and invokes its action', () => {
    const removeCompetition = vi.fn();
    render(<ActiveFilters items={[{ name: 'Competition', value: 'eng Premier League', onRemove: removeCompetition }]}/>);

    expect(screen.getByRole('group', { name: 'Active filters' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Remove Competition filter' }));
    expect(removeCompetition).toHaveBeenCalledOnce();
  });
});
