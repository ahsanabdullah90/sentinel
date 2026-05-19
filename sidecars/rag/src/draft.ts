/* eslint-disable no-console */
import { OllamaClient } from './ollama-client.js';
import { ChromaClient } from './chroma-client.js';

export async function generateDraft(rfpId: string, model: string) {
  console.log(
    JSON.stringify({
      event: 'progress',
      portalId: 'rag',
      message: `Generating draft for ${rfpId} using ${model}...`,
    })
  );

  try {
    const ollama = new OllamaClient();
    const isOllamaUp = await ollama.checkHealth();

    if (!isOllamaUp) {
      throw new Error('Ollama is not running. Please start Ollama.');
    }

    const hasModel = await ollama.isModelPulled(model);
    if (!hasModel) {
      throw new Error(`Model ${model} is not pulled. Please pull it first.`);
    }

    const chroma = new ChromaClient();
    const isChromaUp = await chroma.checkHealth();

    let context = 'No specific context available.';
    if (isChromaUp) {
      // Mock retrieval
      context =
        'The requirement is to provide a comprehensive response focusing on security and local processing.';
    }

    const prompt = `Based on the following context, draft a response.\nContext: ${context}\nRequirement: Draft an executive summary for RFP ${rfpId}.`;

    const response = await ollama.generate(model, prompt, 'You are an expert proposal writer.');

    console.log(
      JSON.stringify({
        event: 'draft_generated',
        data: {
          rfpId,
          section: 'Executive Summary',
          draftText: response,
        },
      })
    );
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(
      JSON.stringify({ level: 'error', msg: 'Draft generation failed', ctx: message })
    );
    console.log(
      JSON.stringify({
        event: 'error',
        code: 'DRAFT_GENERATION_FAILED',
        message,
      })
    );
  }
}
