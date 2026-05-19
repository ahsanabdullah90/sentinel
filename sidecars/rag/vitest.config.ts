import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: ['node_modules/', 'dist/', 'coverage/', '**/*.d.ts', '**/index.ts'],
      lines: 70,
      functions: 70,
      branches: 60,
      statements: 70,
    },
  },
});
