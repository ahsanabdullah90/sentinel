/* eslint-disable no-console */
import axios from 'axios';

export interface GapItem {
  area: string;
  description: string;
  severity: 'blocking' | 'advisory';
  suggestion: string;
}

export async function analyzeGaps(
  rfpText: string,
  config: {
    mode: 'local' | 'cloud',
    model?: string,
    url?: string,
    provider?: string,
    apiKey?: string
  }
): Promise<GapItem[]> {
  console.log(
    JSON.stringify({
      event: 'progress',
      portalId: 'gap-engine',
      message: `Analyzing gaps using ${config.mode} processing...`,
    })
  );

  const prompt = `
    You are a compliance and risk assessment expert. Analyze the following RFP text and identify potential gaps, risks, or missing information that could prevent a successful bid or project execution.
    Focus on:
    1. Security requirements (encryption, certifications).
    2. Compliance (FedRAMP, ISO, SOC2).
    3. Technical feasibility.
    4. Ambiguous timelines or deliverables.

    Respond ONLY with a valid JSON array of objects in this format:
    [
      {
        "area": "Security",
        "description": "Short description of the gap",
        "severity": "blocking" or "advisory",
        "suggestion": "How to mitigate or address this gap"
      }
    ]

    RFP TEXT:
    ${rfpText.substring(0, 10000)}
  `;

  let responseText = '';

  if (config.mode === 'local') {
    const res = await axios.post(`${config.url}/api/generate`, {
      model: config.model,
      prompt: prompt,
      stream: false
    });
    responseText = res.data.response;
  } else {
    // Cloud processing logic would go here, similar to the Rust implementation
    // For the sidecar, we'll assume it's passed the necessary info or called via a central hub
    // To keep it simple, if cloud is selected, we'll suggest using the Rust-based cloud caller
    responseText = '[]';
  }

  try {
    const jsonMatch = responseText.match(/```(?:json)?\s*([\s\S]+?)\s*```/) || [null, responseText];
    const jsonStr = jsonMatch[1].trim();
    const gaps = JSON.parse(jsonStr);

    console.log(
      JSON.stringify({
        event: 'gap_report_generated',
        data: {
          gaps,
        },
      })
    );

    return gaps;
  } catch (err) {
    console.error(JSON.stringify({ level: 'error', msg: 'Failed to parse AI response', ctx: responseText }));
    return [];
  }
}

const args = process.argv.slice(2);

async function main() {
  const rfpIdx = args.indexOf('--rfp-text');
  const modeIdx = args.indexOf('--mode');
  const modelIdx = args.indexOf('--model');
  const urlIdx = args.indexOf('--url');

  if (rfpIdx === -1) {
    console.error(JSON.stringify({ level: 'error', msg: 'Missing --rfp-text argument' }));
    process.exit(1);
  }

  const rfpText = args[rfpIdx + 1];
  const mode = (args[modeIdx + 1] as 'local' | 'cloud') || 'local';
  const model = args[modelIdx + 1] || 'phi3';
  const url = args[urlIdx + 1] || 'http://127.0.0.1:11434';

  await analyzeGaps(rfpText, { mode, model, url });
}

if (process.env.NODE_ENV !== 'test') {
  main().catch((err: unknown) => {
    const message = err instanceof Error ? err.message : String(err);
    console.error(JSON.stringify({ level: 'error', msg: 'Fatal error', ctx: message }));
    process.exit(1);
  });
}
