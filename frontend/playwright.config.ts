import { defineConfig, devices } from '@playwright/test';
import path from 'node:path';

/**
 * End-to-end tests against the real application: the FastAPI backend serving the production
 * build of this frontend, with an empty, throwaway data directory. Run with `npm run e2e`
 * (builds first). No AI provider is configured, so Ask runs in retrieval-only mode.
 */
const PORT = Number(process.env['E2E_PORT'] ?? 8765);
// A fresh data directory per run, so every run starts with an empty library.
const dataDir = path.resolve(__dirname, 'e2e/.data', `run-${Date.now()}`);
const backend = path.resolve(__dirname, '../backend');
const python =
  process.env['DOCUMIND_PYTHON'] ??
  path.join(backend, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1, // one shared server and library
  forbidOnly: !!process.env['CI'],
  retries: 0,
  reporter: process.env['CI'] ? [['list'], ['html', { open: 'never' }]] : 'list',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  globalSetup: './e2e/global-setup.ts',
  webServer: {
    command: `"${python}" -m uvicorn documind.main:create_app --factory --host 127.0.0.1 --port ${PORT}`,
    cwd: backend,
    url: `http://127.0.0.1:${PORT}/api/ready`,
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      DOCUMIND_DATA_DIR: dataDir,
      DOCUMIND_STATIC_DIR: path.resolve(__dirname, 'dist/documind-web/browser'),
      DOCUMIND_LLM_MODEL: '',
      DOCUMIND_LOG_LEVEL: 'WARNING',
    },
  },
});
