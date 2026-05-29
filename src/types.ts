export interface Portal {
  id: string;
  name: string;
  url: string;
  keywords: string;
  status?: string;
  selector_config?: string;
  last_run_at?: string;
  last_run_duration_ms?: number;
  opportunities_count?: number;
  rendering_mode?: string;
  scraper_module?: string;
  cloudflare_bypass_score?: string;
}

export interface Opportunity {
  id: string;
  title: string;
  portal: string;
  date: string;
  issuing_org?: string;
  downloaded_pdf_path?: string | null;
  status?: string;
}
