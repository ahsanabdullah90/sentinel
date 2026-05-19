/* eslint-disable no-console */
/* eslint-disable @typescript-eslint/no-unsafe-call */
/* eslint-disable @typescript-eslint/no-unsafe-member-access */
/* eslint-disable @typescript-eslint/no-unsafe-assignment */
/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-constant-condition */
/* eslint-disable @typescript-eslint/no-unnecessary-condition */
/* eslint-disable @typescript-eslint/restrict-template-expressions */
/* eslint-disable @typescript-eslint/no-unsafe-argument */
import Redis from 'ioredis';

// Cast to any to bypass resolution issues in monorepo linter setup
const redis = new Redis(process.env.REDIS_URL ?? 'redis://localhost:6379') as any;

interface JobData {
  rfpId: string;
}

async function startWorker() {
  console.log('Worker started, listening for jobs...');

  while (true) {
    // BLPOP blocks until a job is available in the 'jobs' list
    const job = await redis.blpop('jobs', 0);
    if (job) {
      const [queue, data] = job;
      console.log(`Processing job from ${queue}:`, data);

      try {
        const parsedData = JSON.parse(data) as JobData;
        console.log(`Running task for RFP: ${parsedData.rfpId}`);
        // Simulate work
        await new Promise((resolve) => setTimeout(resolve, 2000));
        console.log(`Task completed for RFP: ${parsedData.rfpId}`);
      } catch (error: unknown) {
        console.error('Error processing job:', error);
      }
    }
  }
}

startWorker().catch((error: unknown) => {
  console.error('Worker failed:', error);
});
