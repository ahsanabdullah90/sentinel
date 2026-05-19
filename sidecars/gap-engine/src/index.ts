/* eslint-disable no-console */
export function analyzeGaps(rfpId: string) {
  console.log(
    JSON.stringify({
      event: 'progress',
      portalId: 'gap-engine',
      message: `Analyzing gaps for ${rfpId}...`,
    })
  );

  // Stub logic
  const gaps = [
    { area: 'Security', description: 'Missing details on data encryption at rest.' },
    { area: 'Compliance', description: 'FedRAMP level not specified.' },
  ];

  console.log(
    JSON.stringify({
      event: 'gap_report_generated',
      data: {
        rfpId,
        gaps,
      },
    })
  );

  return Promise.resolve(gaps);
}

const args = process.argv.slice(2);
const command = args[0];

async function main() {
  if (command === 'analyze') {
    const rfpIdx = args.indexOf('--rfp');
    if (rfpIdx === -1) {
      console.error(JSON.stringify({ level: 'error', msg: 'Missing --rfp argument' }));
      process.exit(1);
    }
    await analyzeGaps(args[rfpIdx + 1]);
  } else {
    console.log(JSON.stringify({ event: 'status', message: 'Gap Engine stub running.' }));
  }
}

main().catch((err: unknown) => {
  const message = err instanceof Error ? err.message : String(err);
  console.error(JSON.stringify({ level: 'error', msg: 'Fatal error', ctx: message }));
  process.exit(1);
});
