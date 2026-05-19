/* eslint-disable no-console */
import * as dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
// Robust dotenv configuration: search in multiple plausible relative paths
const envPaths = [
  path.resolve(process.cwd(), '.env'),
  path.resolve(__dirname, '../../../.env'),
  path.resolve(__dirname, '../../.env'),
];
for (const p of envPaths) {
  dotenv.config({ path: p });
  if (process.env.GEMINI_API_KEY) {
    break;
  }
}
import { analyzePortal } from './portal-analyzer.js';
import { PortalRunner } from './portal-runner.js';
import { PortalConfig } from './types.js';

const args = process.argv.slice(2);
const command = args[0];

async function main() {
  if (command === 'detect') {
    const urlIdx = args.indexOf('--url');
    if (urlIdx === -1 || urlIdx === args.length - 1) {
      console.error(JSON.stringify({ level: 'error', msg: 'Missing --url argument' }));
      process.exit(1);
    }
    const url = args[urlIdx + 1];

    try {
      const report = await analyzePortal(url);
      console.log(JSON.stringify({ event: 'portal_detected', data: report }));
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      console.log(
        JSON.stringify({ event: 'error', code: 'detect_failed', message })
      );
    }
  } else if (command === 'hunt') {
    const portalIdx = args.indexOf('--portal');

    if (portalIdx === -1 || portalIdx === args.length - 1) {
      console.error(JSON.stringify({ level: 'error', msg: 'Missing --portal argument' }));
      process.exit(1);
    }

    const configIdx = args.indexOf('--config');
    let portalConfig: PortalConfig;
    
    if (configIdx !== -1 && configIdx < args.length - 1) {
      const raw = JSON.parse(args[configIdx + 1]);
      portalConfig = {
        id: raw.id,
        name: raw.name,
        baseUrl: raw.baseUrl || raw.url || 'https://example.com',
        authMethod: raw.authMethod || 'public',
        scraperModule: raw.scraperModule || 'generic_search',
        activeWindowStart: raw.activeWindowStart || '00:00',
        activeWindowEnd: raw.activeWindowEnd || '23:59',
        requestsPerMinute: raw.requestsPerMinute || 15,
        keywords: raw.keywords,
        selectorConfig: raw.selectorConfig || raw.selector_config,
      };
    } else {
      // Fallback to mock if not provided
      const portalId = args[portalIdx + 1];
      portalConfig = {
        id: portalId,
        name: 'Mock Portal',
        baseUrl: 'https://example.com',
        authMethod: 'public',
        scraperModule: 'static_html',
        activeWindowStart: '00:00',
        activeWindowEnd: '23:59',
        requestsPerMinute: 15,
      };
    }

    const runner = new PortalRunner();
    await runner.runPortal(portalConfig);
  } else {
    console.error(JSON.stringify({ level: 'error', msg: `Unknown command: ${command}` }));
    process.exit(1);
  }
}

main().catch((err: unknown) => {
  const ctx = err instanceof Error ? err.message : String(err);
  console.error(JSON.stringify({ level: 'error', msg: 'Fatal error', ctx }));
  process.exit(1);
});
