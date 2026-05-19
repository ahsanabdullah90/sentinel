import { z } from 'zod';

const OllamaTagsResponseSchema = z.object({
  models: z.array(
    z.object({
      name: z.string(),
      model: z.string(),
      size: z.number(),
      digest: z.string(),
    })
  ),
});

export class OllamaClient {
  private baseUrl = 'http://localhost:11434';

  async checkHealth(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/api/tags`);
      return response.ok;
    } catch {
      return false;
    }
  }

  async isModelPulled(modelName: string): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/api/tags`);
      if (!response.ok) return false;

      const data = (await response.json()) as unknown;
      const parsed = OllamaTagsResponseSchema.parse(data);

      return parsed.models.some((m) => m.name === modelName || m.name === `${modelName}:latest`);
    } catch {
      return false;
    }
  }

  // Simplified generate for sprint 1.
  // In a real app we'd stream the response and handle context.
  async generate(model: string, prompt: string, systemContext?: string): Promise<string> {
    const response = await fetch(`${this.baseUrl}/api/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        prompt,
        system: systemContext,
        stream: false,
      }),
    });

    if (!response.ok) {
      throw new Error(`Ollama generation failed: ${response.statusText}`);
    }

    const data = (await response.json()) as { response: string };
    return data.response;
  }
}
