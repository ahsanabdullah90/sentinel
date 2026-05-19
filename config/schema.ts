import { z } from 'zod';

export const ConfigSchema = z.object({
  PORT: z.string().default('50051'),
  CHROMA_URL: z.string().url().default('http://localhost:8000'),
  OLLAMA_URL: z.string().url().default('http://localhost:11434'),
  DATABASE_URL: z.string().default('sqlite:sentinel.db'),
});

export type Config = z.infer<typeof ConfigSchema>;

export function validateConfig(env: Record<string, string | undefined>) {
  return ConfigSchema.parse(env);
}
