import { describe, it, expect } from 'vitest';
import { PortalRunner } from '../src/portal-runner.js';
import type { PortalConfig } from '../src/types.js';

describe('PortalRunner', () => {
  it('runs with mock config without error', async () => {
    const mockConfig: PortalConfig = {
      id: 'test-portal',
      name: 'Test Portal',
      baseUrl: 'https://example.com',
      authMethod: 'public',
      scraperModule: 'static_html',
      activeWindowStart: '00:00',
      activeWindowEnd: '23:59',
      requestsPerMinute: 15,
    };
    const runner = new PortalRunner();
    await expect(runner.runPortal(mockConfig)).resolves.not.toThrow();
  });
});
