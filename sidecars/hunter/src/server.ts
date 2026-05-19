/* eslint-disable no-console */
import 'dotenv/config';
import { initTelemetry } from './telemetry.js';
import * as grpc from '@grpc/grpc-js';

initTelemetry();
import * as protoLoader from '@grpc/proto-loader';
import { analyzePortal } from './portal-analyzer.js';
import { PortalRunner } from './portal-runner.js';
import { PortalConfig } from './types.js';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PROTO_PATH = path.resolve(process.cwd(), 'proto/hunter.proto');

const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true,
});

// eslint-disable-next-line @typescript-eslint/no-explicit-any, @typescript-eslint/no-unsafe-assignment
const hunterProto = grpc.loadPackageDefinition(packageDefinition) as any;

const server = new grpc.Server();

interface GrpcResponse {
  event: string;
  json_payload: string;
}

interface GrpcStream<T> {
  request: T;
  write(message: GrpcResponse): void;
  end(): void;
}

interface DetectRequest {
  url: string;
}

interface HuntRequest {
  portal_id: string;
}

// eslint-disable-next-line @typescript-eslint/no-unsafe-argument, @typescript-eslint/no-unsafe-member-access
server.addService(hunterProto.hunter.HunterService.service, {
  detect: (call: GrpcStream<DetectRequest>) => {
    void (async () => {
      const url = call.request.url;
      try {
        const report = await analyzePortal(url);
        call.write({ event: 'portal_detected', json_payload: JSON.stringify(report) });
        call.end();
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : String(error);
        call.write({ event: 'error', json_payload: JSON.stringify({ message }) });
        call.end();
      }
    })();
  },
  hunt: (call: GrpcStream<HuntRequest>) => {
    void (async () => {
      const portalId = call.request.portal_id;
      const mockConfig: PortalConfig = {
        id: portalId,
        name: 'Mock Portal',
        baseUrl: 'https://example.com',
        authMethod: 'public',
        scraperModule: 'static_html',
        activeWindowStart: '00:00',
        activeWindowEnd: '23:59',
        requestsPerMinute: 15,
      };

      const runner = new PortalRunner();
      try {
        await runner.runPortal(mockConfig);
        call.write({ event: 'hunt_complete', json_payload: JSON.stringify({ success: true }) });
        call.end();
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : String(error);
        call.write({ event: 'error', json_payload: JSON.stringify({ message }) });
        call.end();
      }
    })();
  },
});

const PORT = process.env.PORT ?? 50051;
const bindAddress = '0.0.0.0:' + String(PORT);

server.bindAsync(bindAddress, grpc.ServerCredentials.createInsecure(), (err, port) => {
  if (err) {
    console.error(`Failed to bind server: ${err.message}`);
    return;
  }
  console.log(`Hunter gRPC server running on port ${String(port)}`);
  server.start();
});
