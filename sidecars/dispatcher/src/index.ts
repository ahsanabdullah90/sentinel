/* eslint-disable no-console */
/* eslint-disable @typescript-eslint/no-unsafe-call, @typescript-eslint/no-unsafe-member-access, @typescript-eslint/no-unsafe-assignment */
import Redis from 'ioredis';

const redis = new Redis(process.env.REDIS_URL ?? 'redis://localhost:6379');

async function dispatchJob() {
  const job = { rfpId: 'RFP-123', action: 'scrape' };
  await redis.rpush('jobs', JSON.stringify(job));
  console.log('Dispatched job:', job);
  process.exit(0);
}

dispatchJob().catch((err: unknown) => {
  console.error(err);
});
