/* eslint-disable no-console */
import { ingestDocument } from './ingest.js';
import { generateDraft } from './draft.js';
import { OllamaClient } from './ollama-client.js';

const args = process.argv.slice(2);
const command = args[0];

async function main() {
  if (command === 'health-check') {
    const ollama = new OllamaClient();
    const up = await ollama.checkHealth();
    console.log(
      JSON.stringify({
        event: 'system_status',
        component: 'ollama',
        status: up ? 'online' : 'offline',
      })
    );
  } else if (command === 'ingest') {
    const rfpIdx = args.indexOf('--rfp');
    const fileIdx = args.indexOf('--file');

    if (rfpIdx === -1 || fileIdx === -1) {
      console.error(JSON.stringify({ level: 'error', msg: 'Missing --rfp or --file arguments' }));
      process.exit(1);
    }

    await ingestDocument(args[rfpIdx + 1], args[fileIdx + 1]);
  } else if (command === 'draft') {
    const rfpIdx = args.indexOf('--rfp');
    const modelIdx = args.indexOf('--model');

    if (rfpIdx === -1) {
      console.error(JSON.stringify({ level: 'error', msg: 'Missing --rfp argument' }));
      process.exit(1);
    }

    const model = modelIdx !== -1 ? args[modelIdx + 1] : 'llama3.1:8b';
    await generateDraft(args[rfpIdx + 1], model);
  } else {
    console.error(JSON.stringify({ level: 'error', msg: `Unknown command: ${command}` }));
    process.exit(1);
  }
}

main().catch((err: unknown) => {
  const message = err instanceof Error ? err.message : String(err);
  console.error(JSON.stringify({ level: 'error', msg: 'Fatal error', ctx: message }));
  process.exit(1);
});
