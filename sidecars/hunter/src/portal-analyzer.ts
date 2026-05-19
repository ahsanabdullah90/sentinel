/* eslint-disable no-console */
import { chromium } from 'playwright';
import { PortalViabilityReport } from './types.js';
import { GoogleGenerativeAI } from '@google/generative-ai';

/**
 * Probes a given URL to determine its scrapeability and detect search bars using Gemini API.
 */
export async function analyzePortal(url: string): Promise<PortalViabilityReport> {
  console.log(
    JSON.stringify({
      event: 'progress',
      portalId: 'detector',
      message: `Analyzing ${url} with Gemini...`,
    })
  );

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  let searchSelector = '';

  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });

    // Extract cleaned HTML to save tokens
    const cleanedHtml = await page.evaluate(() => {
      const clone = document.body.cloneNode(true) as HTMLElement;
      const elementsToRemove = clone.querySelectorAll('script, style, noscript, svg, img, iframe');
      elementsToRemove.forEach((el) => el.remove());
      return clone.innerHTML.substring(0, 300000); // Send up to 300k chars of body to avoid giant payloads
    });

    const apiKey = process.env.GEMINI_API_KEY;
    if (apiKey) {
      console.log(
        JSON.stringify({
          event: 'progress',
          portalId: 'detector',
          message: 'Calling Gemini API for intelligent detection...',
        })
      );
      const genAI = new GoogleGenerativeAI(apiKey);

      const prompt = `
        You are an expert web scraper. Analyze the following HTML snippet and find the CSS selector for the main job/opportunity search input field.
        Respond ONLY with a valid JSON object in this exact format:
        { "searchSelector": "your_css_selector_here" }
        If you cannot find a search bar, return:
        { "searchSelector": "" }

        HTML:
        ${cleanedHtml}
      `;

      let result;
      try {
        console.log(
          JSON.stringify({
            event: 'progress',
            portalId: 'detector',
            message: 'Trying gemini-2.5-flash-lite...',
          })
        );
        const model = genAI.getGenerativeModel({ model: 'gemini-2.5-flash-lite' });
        result = await model.generateContent(prompt);
      } catch (err) {
        try {
          console.log(
            JSON.stringify({
              event: 'progress',
              portalId: 'detector',
              message: 'Failed with lite. Trying gemini-2.5-flash...',
            })
          );
          const model = genAI.getGenerativeModel({ model: 'gemini-2.5-flash' });
          result = await model.generateContent(prompt);
        } catch (err2) {
          console.log(
            JSON.stringify({
              event: 'progress',
              portalId: 'detector',
              message: 'Failed with 2.5-flash. Falling back to gemini-1.5-flash...',
            })
          );
          const model = genAI.getGenerativeModel({ model: 'gemini-1.5-flash' });
          result = await model.generateContent(prompt);
        }
      }

      const responseText = result.response.text();

      try {
        // Extract JSON from potential markdown codeblocks
        const jsonMatch = responseText.match(/```(?:json)?\s*([\s\S]+?)\s*```/) || [
          null,
          responseText,
        ];
        const jsonStr = jsonMatch[1].trim();
        const parsed = JSON.parse(jsonStr);
        if (parsed.searchSelector) {
          searchSelector = parsed.searchSelector;
        }
      } catch (parseErr) {
        console.error('Failed to parse Gemini response:', responseText);
      }
    } else {
      console.log(
        JSON.stringify({
          event: 'progress',
          portalId: 'detector',
          message: 'No GEMINI_API_KEY found, falling back to basic heuristics...',
        })
      );
    }

    // Heuristic fallback if Gemini fails or is not available
    if (!searchSelector) {
      console.log(
        JSON.stringify({
          event: 'progress',
          portalId: 'detector',
          message: 'Running heuristic selector detection...',
        })
      );
      searchSelector = await page.evaluate(() => {
        const inputs = Array.from(
          document.querySelectorAll('input[type="text"], input[type="search"], input:not([type])')
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

    await browser.close();

    return {
      url,
      score: searchSelector ? 'good' : 'limited',
      authMethod: 'public',
      renderingMode: 'js_required',
      antiBot: 'none',
      apiAvailable: false,
      searchSelector: searchSelector,
      scrapingOptions: [
        {
          id: 'generic_search',
          label: 'Generic Search Scraper (AI Powered)',
          feasibility: searchSelector ? 'recommended' : 'possible',
          requiresCredential: false,
          description: searchSelector
            ? `AI detected search bar at selector: ${searchSelector}`
            : 'No obvious search bar detected. Manual configuration may be needed.',
        },
      ],
      warnings: searchSelector ? [] : ['No obvious search bar detected.'],
      tosRiskLevel: 'unknown',
    };
  } catch (error: unknown) {
    await browser.close();
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`Failed to analyze portal: ${message}`);
  }
}
