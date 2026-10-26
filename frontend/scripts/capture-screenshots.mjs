// Captures the README screenshots from a running DocuMind (real UI, real API, no mocks).
//
//   node scripts/capture-screenshots.mjs [base-url] [output-dir]
//
// Expects the server to hold the fictional sample documents from backend/tests/eval/dataset.py
// plus an image-only PDF (see docs/DEPLOYMENT.md, "Screenshots"). AI answers are off, so the Ask
// screenshot shows the retrieval-only mode.
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import path from 'node:path';

const base = process.argv[2] ?? 'http://127.0.0.1:8000';
const out = path.resolve(process.argv[3] ?? '../docs/screenshots');
mkdirSync(out, { recursive: true });

const browser = await chromium.launch();

async function shoot(name, viewport, steps) {
  const page = await browser.newPage({ viewport, deviceScaleFactor: 2 });
  await steps(page);
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: path.join(out, `${name}.png`), fullPage: false });
  await page.close();
  console.log(`saved ${name}.png`);
}

const desktop = { width: 1280, height: 800 };
const tall = { width: 1280, height: 1100 };
const phone = { width: 390, height: 844 };

await shoot('library', desktop, async (page) => {
  await page.goto(`${base}/library`);
  await page.getByText('No text found').waitFor();
});

await shoot('search', desktop, async (page) => {
  await page.goto(`${base}/search?q=supplier%20delivery%20delays`);
  await page.locator('mark').first().waitFor();
});

await shoot('reader', tall, async (page) => {
  await page.goto(`${base}/search?q=Kestrel%20Boxes`);
  await page
    .getByRole('link', { name: /at this passage/ })
    .first()
    .click();
  await page.locator('.passage.target').waitFor();
  await page.evaluate(() => window.scrollTo(0, 0)); // header and the opened passage together
});

await shoot('ask', tall, async (page) => {
  await page.goto(`${base}/ask`);
  const question = page.getByLabel('Your question');
  await question.fill('How many days of paid vacation do full-time staff get?');
  await question.press('Enter');
  await page.locator('.entry dm-passage-card').first().waitFor();
  await page.evaluate(() => window.scrollTo(0, 0));
});

await shoot('mobile-search', phone, async (page) => {
  await page.goto(`${base}/search?q=password%20manager`);
  await page.locator('mark').first().waitFor();
  await page.locator('.status').scrollIntoViewIfNeeded();
});

await browser.close();
