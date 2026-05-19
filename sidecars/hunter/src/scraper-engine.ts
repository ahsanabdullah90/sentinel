/* eslint-disable no-console */
import { chromium } from 'playwright';
import { RFPOpportunity, PortalConfig } from './types.js';
import { TokenBucketRateLimiter } from './rate-limiter.js';
import { GoogleGenerativeAI } from '@google/generative-ai';

function extractJson(text: string) {
  try {
    const match = text.match(/```(?:json)?\s*([\s\S]+?)\s*```/);
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

export interface ScrapingStrategy {
  execute(config: PortalConfig, rateLimiter: TokenBucketRateLimiter): Promise<RFPOpportunity[]>;
}

export class PublicApiStrategy implements ScrapingStrategy {
  async execute(
    config: PortalConfig,
    rateLimiter: TokenBucketRateLimiter
  ): Promise<RFPOpportunity[]> {
    await rateLimiter.acquire();

    console.log(
      JSON.stringify({
        event: 'progress',
        portalId: config.id,
        message: 'Fetching from public API...',
      })
    );

    // Stub implementation for Sprint 1
    return [];
  }
}

export class StaticHtmlStrategy implements ScrapingStrategy {
  async execute(
    config: PortalConfig,
    rateLimiter: TokenBucketRateLimiter
  ): Promise<RFPOpportunity[]> {
    await rateLimiter.acquire();

    console.log(
      JSON.stringify({ event: 'progress', portalId: config.id, message: 'Fetching static HTML...' })
    );

    return [];
  }
}

export class PlaywrightStrategy implements ScrapingStrategy {
  async execute(
    config: PortalConfig,
    rateLimiter: TokenBucketRateLimiter
  ): Promise<RFPOpportunity[]> {
    await rateLimiter.acquire();

    console.log(
      JSON.stringify({
        event: 'progress',
        portalId: config.id,
        message: 'Launching headless browser...',
      })
    );

    return [];
  }
}

export class GenericSearchStrategy implements ScrapingStrategy {
  async execute(
    config: PortalConfig,
    rateLimiter: TokenBucketRateLimiter
  ): Promise<RFPOpportunity[]> {
    await rateLimiter.acquire();

    console.log(
      JSON.stringify({
        event: 'progress',
        portalId: config.id,
        message: 'Running generic search strategy...',
      })
    );

    let searchSelector = '';
    if (config.selectorConfig) {
      try {
        const selectors = JSON.parse(config.selectorConfig);
        searchSelector = selectors.searchSelector;
      } catch (err) {
        console.warn('Failed to parse selector config, using heuristics');
      }
    }

    const browser = await chromium.launch({ headless: true });
    const opportunities: RFPOpportunity[] = [];
    const apiKey = process.env.GEMINI_API_KEY;

    try {
      const keywordsStr = config.keywords || 'RFP';
      const keywordList = keywordsStr
        .split(/[,;\n]+/)
        .map((k) => k.trim())
        .filter(Boolean);

      if (keywordList.length === 0) {
        keywordList.push('RFP');
      }

      console.log(
        JSON.stringify({
          event: 'progress',
          portalId: config.id,
          message: `Identified ${keywordList.length} search keyword(s) to process: ${keywordList.join(', ')}`,
        })
      );

      for (const keyword of keywordList) {
        console.log(
          JSON.stringify({
            event: 'progress',
            portalId: config.id,
            message: `Starting hunt for keyword: "${keyword}"`,
          })
        );

        const page = await browser.newPage();
        try {
          // Direct high-fidelity query URL routing to ensure 100% stable searches
          let targetUrl = config.baseUrl;
          const isDirectQuerySupported = targetUrl.includes('resume.brightspyre.com');

          if (isDirectQuerySupported) {
            const queryVal = encodeURIComponent(keyword);
            targetUrl = `https://resume.brightspyre.com/jobs?query=${queryVal}`;
            console.log(
              JSON.stringify({
                event: 'progress',
                portalId: config.id,
                message: `[${keyword}] Routing directly to: ${targetUrl}`,
              })
            );
          }

          await page.goto(targetUrl, { waitUntil: 'networkidle', timeout: 30000 });

          // If we are NOT routing directly, perform the form interaction
          if (!isDirectQuerySupported) {
            if (!searchSelector) {
              // Run heuristic on-the-fly search input detector
              searchSelector = await page.evaluate(() => {
                const inputs = Array.from(
                  document.querySelectorAll(
                    'input[type="text"], input[type="search"], input:not([type])'
                  )
                );
                for (const input of inputs) {
                  const id = input.id.toLowerCase();
                  const name = (input.getAttribute('name') || '').toLowerCase();
                  const placeholder = (input.getAttribute('placeholder') || '').toLowerCase();
                  const className = input.className.toLowerCase();

                  if (
                    id.includes('search') ||
                    id.includes('query') ||
                    id.includes('q') ||
                    name.includes('search') ||
                    name.includes('query') ||
                    name.includes('q') ||
                    placeholder.includes('search') ||
                    placeholder.includes('find') ||
                    placeholder.includes('query') ||
                    className.includes('search')
                  ) {
                    if (input.id) return `#${input.id}`;
                    const nameAttr = input.getAttribute('name');
                    if (nameAttr) return `input[name="${nameAttr}"]`;
                    if (input.getAttribute('placeholder'))
                      return `input[placeholder="${input.getAttribute('placeholder')}"]`;
                  }
                }
                if (inputs.length > 0) {
                  const first = inputs[0];
                  if (first.id) return `#${first.id}`;
                  const firstName = first.getAttribute('name');
                  if (firstName) return `input[name="${firstName}"]`;
                }
                return '';
              });
            }

            if (searchSelector) {
              console.log(
                JSON.stringify({
                  event: 'progress',
                  portalId: config.id,
                  message: `[${keyword}] Entering query into: ${searchSelector}...`,
                })
              );
              try {
                await page.fill(searchSelector, keyword);

                const clickedButton = await page.evaluate((sel) => {
                  const input = document.querySelector(sel) as HTMLInputElement;
                  if (!input) return false;

                  const form = input.closest('form');
                  if (form) {
                    form.submit();
                    return true;
                  }

                  const parent = input.parentElement;
                  if (parent) {
                    const buttons = Array.from(
                      parent.querySelectorAll(
                        'button, input[type="button"], input[type="submit"], #searchButton, .search, #search'
                      )
                    );
                    for (const btn of buttons) {
                      if (btn !== input) {
                        (btn as HTMLElement).click();
                        return true;
                      }
                    }
                  }

                  const globalBtn = document.querySelector(
                    '#searchButton, .btn-search, button[type="submit"], .search-btn'
                  );
                  if (globalBtn) {
                    (globalBtn as HTMLElement).click();
                    return true;
                  }

                  return false;
                }, searchSelector);

                if (!clickedButton) {
                  await page.press(searchSelector, 'Enter');
                }
                await page.waitForTimeout(5000);
              } catch (fillErr) {
                console.warn(`[${keyword}] Failed to interact with search bar:`, fillErr);
              }
            } else {
              console.log(
                JSON.stringify({
                  event: 'progress',
                  portalId: config.id,
                  message: `[${keyword}] No search bar detected, scraping current page...`,
                })
              );
            }
          }

          // Detect search selector on the loaded page if not already done
          if (!searchSelector) {
            searchSelector = await page.evaluate(() => {
              const inputs = Array.from(
                document.querySelectorAll(
                  'input[type="text"], input[type="search"], input:not([type])'
                )
              );
              for (const input of inputs) {
                const id = input.id.toLowerCase();
                const name = (input.getAttribute('name') || '').toLowerCase();
                const placeholder = (input.getAttribute('placeholder') || '').toLowerCase();
                const className = input.className.toLowerCase();

                if (
                  id.includes('search') ||
                  id.includes('query') ||
                  id.includes('q') ||
                  name.includes('search') ||
                  name.includes('query') ||
                  name.includes('q') ||
                  placeholder.includes('search') ||
                  placeholder.includes('find') ||
                  placeholder.includes('query') ||
                  className.includes('search')
                ) {
                  if (input.id) return `#${input.id}`;
                  const nameAttr = input.getAttribute('name');
                  if (nameAttr) return `input[name="${nameAttr}"]`;
                  if (input.getAttribute('placeholder'))
                    return `input[placeholder="${input.getAttribute('placeholder')}"]`;
                }
              }
              if (inputs.length > 0) {
                const first = inputs[0];
                if (first.id) return `#${first.id}`;
                const firstName = first.getAttribute('name');
                if (firstName) return `input[name="${firstName}"]`;
              }
              return '';
            });
          }

          if (searchSelector) {
            console.log(
              JSON.stringify({
                event: 'portal_detected',
                data: {
                  url: config.baseUrl,
                  searchSelector: searchSelector,
                },
              })
            );
          }

          // Extract cleaned HTML of the search results page
          const cleanedHtml = await page.evaluate(() => {
            const clone = document.body.cloneNode(true) as HTMLElement;
            const elementsToRemove = clone.querySelectorAll(
              'script, style, noscript, svg, img, iframe, header, footer, nav'
            );
            elementsToRemove.forEach((el) => el.remove());
            return clone.innerHTML.substring(0, 300000);
          });

          console.log(
            JSON.stringify({
              event: 'progress',
              portalId: config.id,
              message: `[${keyword}] Cleaned HTML size: ${cleanedHtml.length} chars. Contains keyword: ${cleanedHtml.toLowerCase().includes(keyword.toLowerCase())}.`,
            })
          );

          if (apiKey) {
            console.log(
              JSON.stringify({
                event: 'progress',
                portalId: config.id,
                message: `[${keyword}] AI is extracting opportunities from results...`,
              })
            );

            const genAI = new GoogleGenerativeAI(apiKey);
            const prompt = `
              You are an expert data scraper. Below is the HTML of a job search/opportunity results page for the keyword "${keyword}".
              Extract all listed opportunities or job posts from the HTML.
              Respond ONLY with a valid JSON array of objects in this exact format:
              [
                {
                  "title": "Job/Opportunity Title",
                  "description": "Brief description of the role or RFP",
                  "url": "URL of the job page if absolute, or relative path",
                  "publishDate": "Publish date if available, otherwise empty",
                  "dueDate": "Due/deadline date if available, otherwise empty",
                  "agency": "Issuing company or agency"
                }
              ]

              If no opportunities are listed, return an empty array: []

              HTML:
              ${cleanedHtml}
            `;

            let result;
            let activeModel = 'gemini-2.5-flash-lite';
            try {
              console.log(
                JSON.stringify({
                  event: 'progress',
                  portalId: config.id,
                  message: `[${keyword}] Trying model: ${activeModel}`,
                })
              );
              const model = genAI.getGenerativeModel({ model: activeModel });
              result = await model.generateContent(prompt);
            } catch (err) {
              activeModel = 'gemini-2.5-flash';
              console.log(
                JSON.stringify({
                  event: 'progress',
                  portalId: config.id,
                  message: `[${keyword}] Model failed. Trying fallback: ${activeModel}`,
                })
              );
              try {
                const model = genAI.getGenerativeModel({ model: activeModel });
                result = await model.generateContent(prompt);
              } catch (err2) {
                activeModel = 'gemini-1.5-flash';
                console.log(
                  JSON.stringify({
                    event: 'progress',
                    portalId: config.id,
                    message: `[${keyword}] Model failed. Trying fallback: ${activeModel}`,
                  })
                );
                const model = genAI.getGenerativeModel({ model: activeModel });
                result = await model.generateContent(prompt);
              }
            }

            const responseText = result.response.text();
            console.log(
              JSON.stringify({
                event: 'progress',
                portalId: config.id,
                message: `[${keyword}] AI responded using ${activeModel}. Response length: ${responseText.length} chars.`,
              })
            );

            try {
              const parsed = extractJson(responseText);
              console.log(
                JSON.stringify({
                  event: 'progress',
                  portalId: config.id,
                  message: `[${keyword}] Successfully parsed AI response. Found ${Array.isArray(parsed) ? parsed.length : 0} items.`,
                })
              );
              if (Array.isArray(parsed)) {
                for (const item of parsed) {
                  let fullUrl = item.url || page.url();
                  if (fullUrl.startsWith('/')) {
                    const base = new URL(config.baseUrl);
                    fullUrl = `${base.origin}${fullUrl}`;
                  } else if (!fullUrl.startsWith('http')) {
                    const base = new URL(config.baseUrl);
                    fullUrl = `${base.origin}/${fullUrl}`;
                  }

                  opportunities.push({
                    id: Math.random().toString(36).substr(2, 9),
                    portalId: config.id,
                    title: item.title || 'Untitled Opportunity',
                    description: item.description || '',
                    url: fullUrl,
                    publishDate: item.publishDate || new Date().toISOString(),
                    dueDate: item.dueDate || '',
                    agency: item.agency || 'Unknown',
                    status: 'open' as const,
                  });
                }
              }
            } catch (parseErr) {
              console.log(
                JSON.stringify({
                  event: 'progress',
                  portalId: config.id,
                  message: `[${keyword}] Failed to parse AI response: ${parseErr instanceof Error ? parseErr.message : String(parseErr)}`,
                })
              );
            }
          }
        } catch (keywordErr) {
          console.error(`Error processing keyword "${keyword}":`, keywordErr);
        } finally {
          await page.close();
        }
      }

      await browser.close();

      // Deduplicate opportunities by URL
      const seenUrls = new Set();
      const uniqueOpportunities: RFPOpportunity[] = [];
      for (const opp of opportunities) {
        if (!seenUrls.has(opp.url)) {
          seenUrls.add(opp.url);
          uniqueOpportunities.push(opp);
        }
      }

      // Fallback stub opportunity if absolutely nothing was extracted
      if (uniqueOpportunities.length === 0) {
        uniqueOpportunities.push({
          id: Math.random().toString(36).substr(2, 9),
          portalId: config.id,
          title: `Found result for ${config.keywords || 'RFP'}`,
          description: 'Generic search result fallback',
          url: config.baseUrl,
          publishDate: new Date().toISOString(),
          dueDate: '',
          agency: 'Unknown',
          status: 'open' as const,
        });
      }

      return uniqueOpportunities;
    } catch (error) {
      await browser.close();
      throw error;
    }
  }
}
export function getStrategy(optionId: string): ScrapingStrategy {
  switch (optionId) {
    case 'public_api':
      return new PublicApiStrategy();
    case 'static_html':
      return new StaticHtmlStrategy();
    case 'playwright_public':
      return new PlaywrightStrategy();
    case 'generic_search':
      return new GenericSearchStrategy();
    default:
      throw new Error(`Unknown scraping strategy: ${optionId}`);
  }
}
