/* eslint-disable no-console */
import { initTelemetry } from './telemetry.js';
import * as grpc from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';

initTelemetry();
import { ingestDocument } from './ingest.js';
import { OllamaClient } from './ollama-client.js';
import { ChromaClient } from './chroma-client.js';
import * as path from 'path';
import { fileURLToPath } from 'url';
import * as fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PROTO_PATH = path.resolve(process.cwd(), 'proto/rag.proto');

const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true,
});

interface RagProto {
  rag: {
    RagService: {
      service: grpc.ServiceDefinition;
    };
  };
}

const ragProto = grpc.loadPackageDefinition(packageDefinition) as unknown as RagProto;

const server = new grpc.Server();

interface IngestRequest {
  document_id: string;
  content: string;
}

interface QueryRequest {
  query: string;
}

server.addService(ragProto.rag.RagService.service, {
  ingest: (
    call: { request: IngestRequest },
    callback: (err: Error | null, resp?: { status: string }) => void
  ) => {
    void (async () => {
      const { document_id, content } = call.request;
      try {
        const tempFilePath = path.join(__dirname, `../temp_${document_id}.txt`);
        fs.writeFileSync(tempFilePath, content);

        await ingestDocument(document_id, tempFilePath);

        fs.unlinkSync(tempFilePath);

        callback(null, { status: 'ok' });
      } catch (error: unknown) {
        const err = error instanceof Error ? error : new Error(String(error));
        callback(err);
      }
    })();
  },
  query: (
    call: { request: QueryRequest },
    callback: (err: Error | null, resp?: { answer: string; source_documents: string }) => void
  ) => {
    void (async () => {
      const { query } = call.request;
      try {
        const ollama = new OllamaClient();
        const chroma = new ChromaClient();

        let context = 'No specific context available.';
        const isChromaUp = await chroma.checkHealth();
        if (isChromaUp) {
          context =
            'The requirement is to provide a comprehensive response focusing on security and local processing.';
        }

        const prompt = `Based on the following context, answer the query.\nContext: ${context}\nQuery: ${query}`;
        const answer = await ollama.generate(
          'llama3.1:8b',
          prompt,
          'You are an expert proposal assistant.'
        );

        callback(null, {
          answer,
          source_documents: JSON.stringify([{ id: 'mock-1', score: 0.9 }]),
        });
      } catch (error: unknown) {
        const err = error instanceof Error ? error : new Error(String(error));
        callback(err);
      }
    })();
  },
});

const PORT = process.env.PORT ?? 50052;
server.bindAsync(
  `0.0.0.0:${String(PORT)}`,
  grpc.ServerCredentials.createInsecure(),
  (err, port) => {
    if (err) {
      console.error(`Failed to bind server: ${err.message}`);
      return;
    }
    console.log(`RAG gRPC server running on port ${String(port)}`);
    server.start();
  }
);
