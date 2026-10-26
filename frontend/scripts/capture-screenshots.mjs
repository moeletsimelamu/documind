// Captures the README screenshots from a running DocuMind (real UI, real API, no mocks).
//
//   node scripts/capture-screenshots.mjs [base-url] [output-dir]
//
// Expects the server to hold the fictional sample documents from backend/tests/eval/dataset.py
// plus an image-only PDF (see docs/DEPLOYMENT.md, "Screenshots"). AI answers are off, so the Ask
// screenshot shows the retrieval-only mode.
//
// With DOCUMIND_AI_QUESTION set, only the AI-answer screenshot (ask-ai.png) is taken instead: the
// server must have a model configured and documents that answer the question.
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
const aiQuestion = process.env.DOCUMIND_AI_QUESTION;

if (aiQuestion) {
  await shoot('ask-ai', desktop, async (page) => {
    await page.goto(`${base}/ask`);
    const question = page.getByLabel('Your question');
    await question.fill(aiQuestion);
    await question.press('Enter');
    // A local model on a CPU can take a minute or more.
    await page.locator('.answer').waitFor({ timeout: 300_000 });
    await page.locator('.answer .marker').first().click(); // show the first cited source
    await page.locator('.sources-panel li.selected').waitFor();
    await page.locator('.entry').evaluate((entry) => window.scrollTo(0, entry.offsetTop - 16));
  });
  await browser.close();
  process.exit(0);
}

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
  // The original page beside the text, with the opened passage outlined on it.
  await page.getByRole('button', { name: 'Original page', exact: true }).click();
  await page.locator('.page-frame[aria-busy="false"]').waitFor();
  await page.locator('.passage-box').first().waitFor();
  await page.evaluate(() => window.scrollTo(0, 0)); // header and the opened passage together
});

await shoot('ask', tall, async (page) => {
  await page.goto(`${base}/ask`);
  const question = page.getByLabel('Your question');
  await question.fill('How many days of paid vacation do full-time staff get?');
  await question.press('Enter');
  await page.locator('.sources-panel dm-passage-card').first().waitFor();
  await page.evaluate(() => window.scrollTo(0, 0));
});

await shoot('mobile-search', phone, async (page) => {
  await page.goto(`${base}/search?q=password%20manager`);
  await page.locator('mark').first().waitFor();
  await page.locator('.status').scrollIntoViewIfNeeded();
});

await browser.close();
