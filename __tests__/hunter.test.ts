import { describe, it, expect } from 'vitest';
import * as grpc from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

describe('Hunter Integration', () => {
  it('should load proto and create client', async () => {
    const PROTO_PATH = path.resolve(__dirname, '../proto/hunter.proto');
    const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
      keepCase: true,
      longs: String,
      enums: String,
      defaults: true,
      oneofs: true,
    });

    const hunterProto = grpc.loadPackageDefinition(packageDefinition) as any;
    expect(hunterProto.hunter).toBeDefined();
    expect(hunterProto.hunter.HunterService).toBeDefined();

    const client = new hunterProto.hunter.HunterService(
      'localhost:50051',
      grpc.credentials.createInsecure()
    );
    expect(client).toBeDefined();
  });
});
