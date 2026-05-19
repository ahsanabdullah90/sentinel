/* eslint-disable no-console */
import { ChromaClient } from './chroma-client.js';
import * as fs from 'fs';
import * as path from 'path';

// Note: In Sprint 1, we stub actual document extraction for speed,
// but lay out the pipeline structure.

export async function ingestDocument(rfpId: string, filePath: string) {
  console.log(
    JSON.stringify({
      event: 'progress',
      portalId: 'rag',
      message: `Starting ingestion for ${filePath}`,
    })
  );

  if (!fs.existsSync(filePath)) {
    throw new Error(`File not found: ${filePath}`);
  }

  const ext = path.extname(filePath).toLowerCase();

  console.log(
    JSON.stringify({ event: 'progress', portalId: 'rag', message: `Parsing ${ext} file...` })
  );

  // 1. Stub extraction (would use pdf-parse, mammoth, xlsx)
  const extractedText = `This is mock extracted text for RFP ${rfpId} from ${filePath}.`;

  console.log(JSON.stringify({ event: 'progress', portalId: 'rag', message: 'Chunking text...' }));

  // 2. Stub chunking
  const chunks = [{ text: extractedText, id: `${rfpId}-chunk-0` }];

  console.log(
    JSON.stringify({
      event: 'progress',
      portalId: 'rag',
      message: 'Generating embeddings and storing...',
    })
  );

  // 3. Store in Chroma
  try {
    const chroma = new ChromaClient();
    const isChromaUp = await chroma.checkHealth();

    if (isChromaUp) {
      // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
      const collection = await chroma.getOrCreateCollection(`rfp_${rfpId}`);
      // Using mock embeddings for speed, real app would call Ollama nomic-embed-text
      // eslint-disable-next-line @typescript-eslint/no-unsafe-call, @typescript-eslint/no-unsafe-member-access
      await collection.upsert({
        ids: chunks.map((c) => c.id),
        documents: chunks.map((c) => c.text),
        metadatas: chunks.map((_, i) => ({ chunkIndex: i, source: filePath })),
      });
    } else {
      console.log(
        JSON.stringify({
          event: 'warning',
          message: 'ChromaDB is not running. Ingestion skipped storage phase.',
        })
      );
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(JSON.stringify({ level: 'error', msg: 'Ingestion failed', ctx: message }));
    throw err;
  }

  console.log(
    JSON.stringify({
      event: 'progress',
      portalId: 'rag',
      message: `Ingestion complete. Processed ${String(chunks.length)} chunks.`,
    })
  );

  return { chunksProcessed: chunks.length };
}
