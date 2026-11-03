import { afterEach, describe, expect, it, vi } from 'vitest';
import { v2Api } from './v2Api';

afterEach(() => vi.unstubAllGlobals());

describe('v2 API request scheduling', () => {
  it('keeps local analytics requests sequential to avoid SQLite read bursts', async () => {
    let active = 0;
    let maximumActive = 0;
    const fetchMock = vi.fn(async () => {
      active += 1;
      maximumActive = Math.max(maximumActive, active);
      await new Promise(resolve => setTimeout(resolve, 10));
      active -= 1;
      return { ok: true, json: async () => ({}) } as Response;
    });
    vi.stubGlobal('fetch', fetchMock);

    await Promise.all([v2Api.coverage(), v2Api.sources(), v2Api.identitySummary()]);

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(maximumActive).toBe(1);
  });
});
