/* eslint-disable no-console */
import { chromium, Browser, Page } from 'playwright';
import { RFPOpportunity, PortalConfig } from './types.js';
import { TokenBucketRateLimiter } from './rate-limiter.js';
import { GoogleGenerativeAI } from '@google/generative-ai';

function extractJson(text: string) {
  try {
    const match = text.match(/\`\`\`(?:json)?\s*([\s\S]+?)\s*\`\`\`/);
    const raw = match ? match[1] : text;
    return JSON.parse(raw.trim());
  } catch (err) {
    const start = text.indexOf('{') !== -1 ? text.indexOf('{') : text.indexOf('[');
    const end = text.lastIndexOf('}') !== -1 ? text.lastIndexOf('}') : text.lastIndexOf(']');
    if (start !== -1 && end !== -1 && end > start) {
      try {
        return JSON.parse(text.substring(start, end + 1));
      } catch (e) {
        throw new Error(`Failed to parse: ${err instanceof Error ? err.message : String(err)}`);
      }
    }
    throw err;
  }
}

async function handleLogin(page: Page, config: PortalConfig) {
  if (config.authMethod !== 'login' && config.authMethod !== 'credential') return;
  if (!config.credentials?.username || !config.credentials?.password) {
    console.warn(`[${config.id}] Login requested but credentials missing.`);
    return;
  }

  console.log(JSON.stringify({ event: 'progress', portalId: config.id, message: 'Attempting login...' }));

  // Intelligent login detection
  const loginFormSelectors = ['input[type="password"]', 'input[name*="pass"]', 'input[id*="pass"]'];
  let passwordInputFound = false;

  for (const selector of loginFormSelectors) {
    if (await page.$(selector)) {
      passwordInputFound = true;
      break;
    }
  }

  if (passwordInputFound) {
    try {
      // Find username field - often near password
      await page.fill('input[type="text"], input[type="email"], input[name*="user"], input[name*="email"]', config.credentials.username);
      await page.fill('input[type="password"]', config.credentials.password);
      await page.click('button[type="submit"], input[type="submit"], button:has-text("Login"), button:has-text("Sign In")');
      await page.waitForNavigation({ waitUntil: 'networkidle', timeout: 15000 }).catch(() => {});
      console.log(JSON.stringify({ event: 'progress', portalId: config.id, message: 'Login flow completed.' }));
    } catch (err) {
      console.error(`[${config.id}] Login failed: `, err);
    }
  }
}

export interface ScrapingStrategy {
  execute(config: PortalConfig, rateLimiter: TokenBucketRateLimiter): Promise<RFPOpportunity[]>;
}

export class PublicApiStrategy implements ScrapingStrategy {
  async execute(config: PortalConfig, rateLimiter: TokenBucketRateLimiter): Promise<RFPOpportunity[]> {
    await rateLimiter.acquire();
    console.log(JSON.stringify({ event: 'progress', portalId: config.id, message: 'Fetching from public API...' }));
    return [];
  }
}

export class StaticHtmlStrategy implements ScrapingStrategy {
  async execute(config: PortalConfig, rateLimiter: TokenBucketRateLimiter): Promise<RFPOpportunity[]> {
    await rateLimiter.acquire();
    console.log(JSON.stringify({ event: 'progress', portalId: config.id, message: 'Fetching static HTML...' }));
    return [];
  }
}

export class GenericSearchStrategy implements ScrapingStrategy {
  async execute(config: PortalConfig, rateLimiter: TokenBucketRateLimiter): Promise<RFPOpportunity[]> {
    await rateLimiter.acquire();
    console.log(JSON.stringify({ event: 'progress', portalId: config.id, message: 'Running generic search strategy...' }));

    const browser = await chromium.launch({ headless: true });
    const opportunities: RFPOpportunity[] = [];
    const apiKey = process.env.GEMINI_API_KEY;

    try {
      const page = await browser.newPage();
      await page.goto(config.baseUrl, { waitUntil: 'networkidle' });

      await handleLogin(page, config);

      const keywordList = (config.keywords || 'RFP').split(/[,;\n]+/).map(k => k.trim()).filter(Boolean);

      for (const keyword of keywordList) {
        await rateLimiter.acquire();
        // Custom logic for specific sites if needed
        if (config.baseUrl.includes('tenderalert.pk')) {
           // Direct search navigation for tenderalert
           await page.goto(`${config.baseUrl}/search?q=${encodeURIComponent(keyword)}`, { waitUntil: 'networkidle' });
        } else if (config.baseUrl.includes('rozee.pk')) {
           await page.goto(`https://www.rozee.pk/job/jsearch/q/${encodeURIComponent(keyword)}`, { waitUntil: 'networkidle' });
        } else if (config.baseUrl.includes('mustakbil.com')) {
           await page.goto(`https://www.mustakbil.com/jobs/search/${encodeURIComponent(keyword)}`, { waitUntil: 'networkidle' });
        } else {
           // Generic heuristic search
           const searchInput = await page.$('input[type="text"], input[type="search"]');
           if (searchInput) {
             await searchInput.fill(keyword);
             await searchInput.press('Enter');
             await page.waitForNavigation({ waitUntil: 'networkidle' }).catch(() => {});
           }
        }

        const cleanedHtml = await page.evaluate(() => {
          const clone = document.body.cloneNode(true) as HTMLElement;
          const toRemove = clone.querySelectorAll('script, style, noscript, svg, img, iframe, header, footer, nav');
          toRemove.forEach(el => el.remove());
          return clone.innerHTML.substring(0, 200000);
        });

        if (apiKey) {
           const genAI = new GoogleGenerativeAI(apiKey);
           const model = genAI.getGenerativeModel({ model: 'gemini-1.5-flash' });
           const prompt = `Extract job/opportunity listings for "${keyword}" from this HTML as JSON array: [{title, description, url, agency}]. HTML: ${cleanedHtml}`;
           const result = await model.generateContent(prompt);
           const parsed = extractJson(result.response.text());
           if (Array.isArray(parsed)) {
             parsed.forEach(item => {
               opportunities.push({
                 id: Math.random().toString(36).substr(2, 9),
                 portalId: config.id,
                 title: item.title || 'Untitled',
                 description: item.description || '',
                 url: item.url.startsWith('http') ? item.url : new URL(item.url, config.baseUrl).href,
                 publishDate: new Date().toISOString(),
                 dueDate: '',
                 agency: item.agency || 'Unknown',
                 status: 'open'
               });
             });
           }
        } else {
          // Fallback minimal extraction
          opportunities.push({
            id: Math.random().toString(36).substr(2, 9),
            portalId: config.id,
            title: `Potential match for ${keyword}`,
            description: 'AI extraction skipped (no API key)',
            url: page.url(),
            publishDate: new Date().toISOString(),
            dueDate: '',
            agency: 'Unknown',
            status: 'open'
          });
        }
      }
      await browser.close();
      return opportunities;
    } catch (err) {
      await browser.close();
      throw err;
    }
  }
}

export function getStrategy(optionId: string): ScrapingStrategy {
  switch (optionId) {
    case 'public_api': return new PublicApiStrategy();
    case 'static_html': return new StaticHtmlStrategy();
    case 'generic_search':
    case 'playwright_public': return new GenericSearchStrategy();
    default: throw new Error(`Unknown scraping strategy: ${optionId}`);
  }
}
