import { describe, it, expect } from 'vitest';
import * as grpc from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

describe('RAG Integration', () => {
  it('should load proto and create client', async () => {
    const PROTO_PATH = path.resolve(__dirname, '../proto/rag.proto');
    const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
      keepCase: true,
      longs: String,
      enums: String,
      defaults: true,
      oneofs: true,
    });

    const ragProto = grpc.loadPackageDefinition(packageDefinition) as any;
    expect(ragProto.rag).toBeDefined();
    expect(ragProto.rag.RagService).toBeDefined();

    const client = new ragProto.rag.RagService(
      'localhost:50052',
      grpc.credentials.createInsecure()
    );
    expect(client).toBeDefined();
  });
});
