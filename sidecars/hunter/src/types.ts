export interface PortalConfig {
  id: string;
  name: string;
  baseUrl: string;
  authMethod: 'public' | 'login' | 'mfa';
  scraperModule: string;
  activeWindowStart: string;
  activeWindowEnd: string;
  requestsPerMinute: number;
  keywords?: string;
  selectorConfig?: string; // JSON string of selectors
}

export interface RFPOpportunity {
  id: string;
  portalId: string;
  title: string;
  description: string;
  url: string;
  publishDate: string;
  dueDate: string;
  agency: string;
  status: 'open' | 'closed' | 'archived';
  rawHtml?: string;
}

export interface PortalAnalysisReport {
  isSupported: boolean;
  requiresAuth: boolean;
  hasCaptcha: boolean;
  platformType: string;
}

export type PortalAuthMethod = 'public' | 'api_key' | 'credential' | 'oauth';
export type PortalRenderingMode = 'static' | 'js_required';
export type PortalAntiBot = 'none' | 'captcha' | 'cloudflare' | 'aggressive';
export type ScrapingFeasibility = 'recommended' | 'possible' | 'risky';

export interface ScrapingOption {
  id: string;
  label: string;
  feasibility: ScrapingFeasibility;
  requiresCredential: boolean;
  description: string;
}

export type PortalViabilityScore = 'excellent' | 'good' | 'limited' | 'blocked';

export interface PortalViabilityReport {
  url: string;
  score: PortalViabilityScore;
  authMethod: PortalAuthMethod;
  renderingMode: PortalRenderingMode;
  antiBot: PortalAntiBot;
  apiAvailable: boolean;
  apiEndpoint?: string;
  loginUrl?: string;
  detectedPlatform?: string;
  scrapingOptions: ScrapingOption[];
  warnings: string[];
  tosRiskLevel: 'low' | 'medium' | 'high' | 'unknown';
  searchSelector?: string;
}
