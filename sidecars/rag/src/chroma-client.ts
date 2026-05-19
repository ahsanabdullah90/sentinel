/* eslint-disable @typescript-eslint/no-unsafe-assignment, @typescript-eslint/no-unsafe-call, @typescript-eslint/no-unsafe-member-access, @typescript-eslint/no-unsafe-return */
import { ChromaClient as BaseChromaClient } from 'chromadb';

export class ChromaClient {
  private client: BaseChromaClient;

  constructor() {
    this.client = new BaseChromaClient({ path: 'http://localhost:8000' });
  }

  async checkHealth(): Promise<boolean> {
    try {
      const heartbeat = await this.client.heartbeat();
      return typeof heartbeat === 'number';
    } catch {
      return false;
    }
  }

  async getOrCreateCollection(name: string) {
    return await this.client.getOrCreateCollection({
      name,
      metadata: { 'hnsw:space': 'cosine' },
    });
  }
}
