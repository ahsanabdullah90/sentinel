import { describe, it, expect } from 'vitest';
import { Opportunity } from '../src/types';

describe('Opportunity Interface & Data Schema', () => {
  it('should correctly structure an Opportunity object conforming to the schema', () => {
    const mockOpportunity: Opportunity = {
      id: 'test-opp-id',
      title: 'Full Stack Engineer',
      portal: 'Resume Brightspyre',
      date: '2026-06-01',
      issuing_org: 'Brightspyre Corp',
      status: 'new',
      url: 'https://resume.brightspyre.com/jobs/123',
      portal_base_url: 'https://resume.brightspyre.com',
      description: 'Super awesome job description for RFP evaluation.',
    };

    expect(mockOpportunity.id).toBe('test-opp-id');
    expect(mockOpportunity.title).toBe('Full Stack Engineer');
    expect(mockOpportunity.portal).toBe('Resume Brightspyre');
    expect(mockOpportunity.date).toBe('2026-06-01');
    expect(mockOpportunity.issuing_org).toBe('Brightspyre Corp');
    expect(mockOpportunity.status).toBe('new');
    expect(mockOpportunity.url).toBe('https://resume.brightspyre.com/jobs/123');
    expect(mockOpportunity.portal_base_url).toBe('https://resume.brightspyre.com');
    expect(mockOpportunity.description).toBe('Super awesome job description for RFP evaluation.');
  });

  it('should support optional properties on Opportunity correctly', () => {
    const mockOpportunity: Opportunity = {
      id: 'another-opp-id',
      title: 'Short Job Title',
      portal: 'Example Portal',
      date: '2026-06-01',
    };

    expect(mockOpportunity.issuing_org).toBeUndefined();
    expect(mockOpportunity.url).toBeUndefined();
    expect(mockOpportunity.description).toBeUndefined();
    expect(mockOpportunity.downloaded_pdf_path).toBeUndefined();
  });
});

