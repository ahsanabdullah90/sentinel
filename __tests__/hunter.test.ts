import { describe, it, expect } from 'vitest';
import { Portal } from '../src/types';

describe('Portal Interface & Configuration Schema', () => {
  it('should correctly structure a Portal object conforming to the schema', () => {
    const mockPortal: Portal = {
      id: 'test-portal-id',
      name: 'Resume Brightspyre',
      url: 'https://resume.brightspyre.com',
      keywords: 'engineer, developer',
      status: 'active',
      rendering_mode: 'static',
      scraper_module: 'default',
    };

    expect(mockPortal.id).toBe('test-portal-id');
    expect(mockPortal.name).toBe('Resume Brightspyre');
    expect(mockPortal.url).toBe('https://resume.brightspyre.com');
    expect(mockPortal.keywords).toBe('engineer, developer');
    expect(mockPortal.status).toBe('active');
    expect(mockPortal.rendering_mode).toBe('static');
    expect(mockPortal.scraper_module).toBe('default');
  });

  it('should support optional properties correctly', () => {
    const mockPortal: Portal = {
      id: 'another-portal-id',
      name: 'Test Portal',
      url: 'https://example.com',
      keywords: 'test',
    };

    expect(mockPortal.status).toBeUndefined();
    expect(mockPortal.last_run_duration_ms).toBeUndefined();
    expect(mockPortal.opportunities_count).toBeUndefined();
  });
});

