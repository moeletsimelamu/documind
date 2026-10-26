import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

/**
 * Automated accessibility audit (axe-core, WCAG 2.0–2.2 A and AA rules) of every page in the
 * states a user sees. Automated rules catch only part of WCAG; keyboard and visual checks are
 * recorded in docs/REVIEW.md. Creates its own document and removes it again, so the workflow
 * suite still starts with an empty library.
 */
test.describe.configure({ mode: 'serial' });

const WCAG = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
let documentId = '';

async function audit(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page }).withTags(WCAG).analyze();
  const problems = results.violations.map(
    (v) => `${v.impact} ${v.id}: ${v.help} (${v.nodes.map((n) => n.target.join(' ')).join(', ')})`,
  );
  expect(problems, 'accessibility violations').toEqual([]);
}

test.beforeAll(async ({ request }) => {
  const response = await request.post('/api/documents', {
    multipart: {
      file: {
        name: 'accessibility-check.txt',
        mimeType: 'text/plain',
        buffer: Buffer.from(
          'Accessibility check\n\nThe warehouse audit found three fire-exit signs missing.\n',
        ),
      },
    },
  });
  expect(response.status()).toBe(202);
  documentId = (await response.json()).id;
  await expect
    .poll(async () => (await (await request.get(`/api/documents/${documentId}`)).json()).status)
    .toBe('ready');
});

test.afterAll(async ({ request }) => {
  if (documentId) {
    await request.delete(`/api/documents/${documentId}`);
  }
});

test('library', async ({ page }) => {
  await page.goto('/library');
  await expect(page.getByRole('link', { name: 'accessibility-check.txt' })).toBeVisible();
  await audit(page);
});

test('delete confirmation dialog', async ({ page }) => {
  await page.goto('/library');
  await page.getByRole('button', { name: 'Delete accessibility-check.txt' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await audit(page);
  await page.keyboard.press('Escape');
});

test('document reader opened at a passage', async ({ page }) => {
  await page.goto('/search?q=warehouse');
  await page
    .getByRole('link', { name: /at this passage/ })
    .first()
    .click();
  await expect(page.locator('.passage.target')).toBeVisible();
  await audit(page);
});

test('search results', async ({ page }) => {
  await page.goto('/search?q=fire%20exit');
  await expect(page.locator('mark').first()).toBeVisible();
  await audit(page);
});

test('ask with a response', async ({ page }) => {
  await page.goto('/ask');
  await page.getByLabel('Your question').fill('What did the warehouse audit find?');
  await page.getByLabel('Your question').press('Enter');
  await expect(page.locator('.sources-panel dm-passage-card').first()).toBeVisible();
  await audit(page);
});

test('not-found page', async ({ page }) => {
  await page.goto('/missing-page');
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
  await audit(page);
});
