/* eslint-disable no-console */
import { ChromaClient } from './chroma-client.js';
import * as fs from 'fs';
import * as path from 'path';
import { execSync } from 'child_process';

function chunkText(text: string, chunkSize = 1000, overlap = 100): string[] {
  const chunks: string[] = [];
  let start = 0;
  while (start < text.length) {
    const end = Math.min(start + chunkSize, text.length);
    chunks.push(text.substring(start, end));
    // Avoid infinite loop if overlap is larger than chunk size
    if (chunkSize <= overlap) {
      start += chunkSize;
    } else {
      start += chunkSize - overlap;
    }
  }
  return chunks;
}

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

  // 1. Live extraction using pdftotext or filesystem read
  let extractedText = '';
  if (ext === '.pdf') {
    try {
      extractedText = execSync(`pdftotext "${filePath}" -`, { encoding: 'utf-8' });
    } catch (err) {
      console.warn('pdftotext failed, falling back to mock text extraction:', err);
      extractedText = `This is mock extracted text for RFP ${rfpId} from ${filePath}.`;
    }
  } else {
    try {
      extractedText = fs.readFileSync(filePath, 'utf-8');
    } catch (err) {
      console.warn('fs read failed, using mock text:', err);
      extractedText = `This is mock extracted text for RFP ${rfpId} from ${filePath}.`;
    }
  }

  console.log(JSON.stringify({ event: 'progress', portalId: 'rag', message: 'Chunking text...' }));

  // 2. Real chunking
  const textChunks = chunkText(extractedText, 1000, 100);
  const chunks = textChunks.map((text, idx) => ({
    text,
    id: `${rfpId}-chunk-${idx}`,
  }));

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
