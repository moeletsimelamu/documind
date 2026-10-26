import { existsSync, readdirSync, rmSync } from 'node:fs';
import path from 'node:path';

/** Checks the production build exists, and removes data left by earlier runs (best effort). */
export default function globalSetup(): void {
  if (!existsSync(path.resolve(__dirname, '../dist/documind-web/browser/index.html'))) {
    throw new Error('Build the frontend first: npm run build (or use npm run e2e).');
  }
  const data = path.resolve(__dirname, '.data');
  const runs = existsSync(data) ? readdirSync(data).sort() : [];
  for (const run of runs.slice(0, -1)) {
    try {
      rmSync(path.join(data, run), { recursive: true, force: true });
    } catch {
      // still in use (e.g. a server from an aborted run); removed on a later run
    }
  }
}
