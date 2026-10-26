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
let pdfId = '';

/** A one-page PDF with a line of Helvetica text (a standard font pdf.js loads from the site). */
function onePagePdf(line: string): Buffer {
  const nl = String.fromCharCode(10);
  const stream = `BT /F1 14 Tf 72 720 Td (${line}) Tj ET`;
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] ' +
      '/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    [`<< /Length ${stream.length} >>`, 'stream', stream, 'endstream'].join(nl),
  ];
  let body = '%PDF-1.4' + nl;
  const offsets: number[] = [];
  objects.forEach((object, i) => {
    offsets.push(body.length);
    body += [`${i + 1} 0 obj`, object, 'endobj', ''].join(nl);
  });
  const xref = body.length;
  const entries = offsets.map((o) => `${String(o).padStart(10, '0')} 00000 n `);
  body += ['xref', `0 ${objects.length + 1}`, '0000000000 65535 f ', ...entries, ''].join(nl);
  body += ['trailer', `<< /Size ${objects.length + 1} /Root 1 0 R >>`, 'startxref'].join(nl);
  body += [nl + String(xref), '%%EOF', ''].join(nl);
  return Buffer.from(body, 'latin1');
}

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
  const pdf = await request.post('/api/documents', {
    multipart: {
      file: {
        name: 'accessibility-dock.pdf',
        mimeType: 'application/pdf',
        buffer: onePagePdf('The loading dock inspection found two blocked doorways.'),
      },
    },
  });
  expect(pdf.status()).toBe(202);
  pdfId = (await pdf.json()).id;
  for (const id of [documentId, pdfId]) {
    await expect
      .poll(async () => (await (await request.get(`/api/documents/${id}`)).json()).status)
      .toBe('ready');
  }
});

test.afterAll(async ({ request }) => {
  for (const id of [documentId, pdfId].filter(Boolean)) {
    await request.delete(`/api/documents/${id}`);
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

test('PDF reader with find and the original page open', async ({ page }) => {
  await page.goto(`/documents/${pdfId}?q=blocked%20doorways`);
  await expect(page.locator('.match-count')).toHaveText('1 of 1');
  await page.getByRole('button', { name: 'Original page', exact: true }).click();
  await expect(page.locator('.page-frame')).toHaveAttribute('aria-busy', 'false');
  await expect(page.locator('.passage-box').first()).toBeVisible();
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
