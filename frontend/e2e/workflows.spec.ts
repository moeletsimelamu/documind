import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';

/**
 * Complete user workflows through the real UI and API. Tests run in order and share one library:
 * each step builds on the documents the previous ones uploaded.
 */
test.describe.configure({ mode: 'serial' });

// Any console error or uncaught exception fails the test. This is also how a blocked resource
// (for example a content-security-policy violation) shows up. Chromium also logs every 4xx
// response; those are expected rejections (e.g. a duplicate upload) that the UI handles and the
// tests assert on, so only they are ignored. 5xx responses still fail.
const EXPECTED_CLIENT_ERROR =
  /^Failed to load resource: the server responded with a status of 4\d\d/;
let browserErrors: string[] = [];
test.beforeEach(({ page }) => {
  browserErrors = [];
  page.on('console', (message) => {
    if (message.type() === 'error' && !EXPECTED_CLIENT_ERROR.test(message.text())) {
      browserErrors.push(message.text());
    }
  });
  page.on('pageerror', (error) => browserErrors.push(error.message));
});
test.afterEach(() => {
  expect(browserErrors, 'browser console errors').toEqual([]);
});

const fixture = (name: string) => ({
  name,
  mimeType: 'application/pdf',
  buffer: readFileSync(path.join(__dirname, 'fixtures', name)),
});
const NOTES = {
  name: 'board-notes.txt',
  mimeType: 'text/plain',
  buffer: Buffer.from(
    'Board meeting, 3 October\n\nThe board approved a hiring freeze until March.\n' +
      'Supplier delays at the Durban port slowed deliveries for six weeks.\n',
  ),
};

async function upload(page: Page, files: Parameters<Page['setInputFiles']>[1]): Promise<void> {
  await page.locator('input[type=file]').setInputFiles(files);
}

function row(page: Page, name: string) {
  return page.locator('tbody tr', { has: page.getByRole('link', { name, exact: true }) });
}

test('starts with an empty library that explains what to do', async ({ page }) => {
  await page.goto('/');

  await expect(page).toHaveURL(/\/library$/);
  await expect(page.getByRole('heading', { name: 'Your library is empty' })).toBeVisible();
  await expect(page.getByText('0 documents')).toBeVisible();
});

test('uploads documents, shows processing outcomes and rejects unsupported files', async ({
  page,
}) => {
  await page.goto('/library');

  await upload(page, [
    fixture('falcon-steering-minutes.pdf'),
    NOTES,
    fixture('scanned-invoice.pdf'),
    { name: 'contract.docx', mimeType: 'application/octet-stream', buffer: Buffer.from('PK') },
  ]);

  const queue = page.locator('.queue');
  await expect(queue.getByText('Only PDF and TXT files can be uploaded.')).toBeVisible();
  await expect(queue.getByText('Indexed and searchable.')).toHaveCount(2);
  await expect(queue.getByText(/appears to contain scanned images/)).toBeVisible();

  await expect(row(page, 'falcon-steering-minutes.pdf')).toContainText('Ready');
  await expect(row(page, 'board-notes.txt')).toContainText('Ready');
  await expect(row(page, 'scanned-invoice.pdf')).toContainText('No text found');
  await expect(page.getByText('3 documents')).toBeVisible();
});

test('rejects a duplicate upload and links to the original', async ({ page }) => {
  await page.goto('/library');

  await upload(page, { ...NOTES, name: 'board-notes-copy.txt' });

  const message = page.locator('.queue').getByText(/already in your library as “board-notes.txt”/);
  await expect(message).toBeVisible();
  await page.locator('.queue').getByRole('link', { name: 'Open it' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'board-notes.txt' })).toBeVisible();
});

test('searches from the top bar and opens a result at its passage', async ({ page }) => {
  await page.goto('/library');

  await page
    .getByRole('searchbox', { name: 'Search your documents' })
    .fill('Lumen Systems partner');
  await page.keyboard.press('Enter');

  await expect(page).toHaveURL(/\/search\?q=Lumen/);
  const result = page.locator('dm-passage-card').first();
  await expect(result).toContainText('falcon-steering-minutes.pdf');
  await expect(result).toContainText('p. 2');
  // The best-matching sentence is highlighted; matched words are underlined (or marked, in a
  // one-sentence excerpt).
  await expect(result.locator('.term, mark:not(.best)').first()).toHaveText('Lumen');

  await result.getByRole('link', { name: /at this passage/ }).click();

  await expect(page).toHaveURL(/\/documents\/.+\?chunk=\d+/);
  const target = page.locator('.passage.target');
  await expect(target).toContainText('Lumen Systems');
  await expect(target).toBeFocused();
});

test('a document link still works after a full page reload', async ({ page }) => {
  await page.goto('/library');
  await page.getByRole('link', { name: 'falcon-steering-minutes.pdf', exact: true }).click();
  await expect(page.getByText('PAGE 1', { exact: false })).toBeVisible();

  await page.reload();

  await expect(
    page.getByRole('heading', { level: 1, name: 'falcon-steering-minutes.pdf' }),
  ).toBeVisible();
  await expect(page.locator('.passage').first()).toContainText('Project Falcon');
});

test('answers with relevant passages, or says the documents do not contain the answer', async ({
  page,
}) => {
  await page.goto('/ask');
  await expect(page.getByText('AI answers are off on this server')).toBeVisible();
  const question = page.getByLabel('Your question');

  await question.fill('What budget did the committee approve for Project Falcon?');
  await question.press('Enter');

  const answered = page.locator('.entry').last();
  await expect(answered.locator('.response-label')).toContainText('Relevant passages');
  await expect(answered.locator('.closest blockquote')).toContainText('R4.5 million');
  // Wide screen: the sources of the active question are in the panel beside the thread.
  await expect(page.locator('.sources-panel dm-passage-card').first()).toContainText(
    'R4.5 million',
  );
  await expect(question).toHaveValue('');

  await question.fill('Who won the rugby world cup?');
  await question.press('Enter');

  await expect(page.locator('.entry').last()).toContainText(
    'Not enough in your documents to answer this',
  );
  await expect(page.locator('.entry').first()).toContainText('Relevant passages');
});

test('deletes a document after confirmation, and it disappears from search', async ({ page }) => {
  await page.goto('/library');

  await page.getByRole('button', { name: 'Delete board-notes.txt' }).click();
  const dialog = page.getByRole('dialog', { name: 'Delete this document?' });
  await expect(dialog).toContainText('board-notes.txt');
  await dialog.getByRole('button', { name: 'Delete' }).click();

  await expect(dialog).toBeHidden();
  await expect(page.getByRole('status').or(page.locator('.toast'))).toContainText(
    'Deleted “board-notes.txt”',
  );
  await expect(row(page, 'board-notes.txt')).toHaveCount(0);

  await page.goto('/search?q=Durban');
  await expect(page.getByText('No passages contain these words')).toBeVisible();
});

test('shows a not-found page for unknown addresses', async ({ page }) => {
  await page.goto('/no/such/page');

  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
  await page.getByRole('link', { name: 'Go to the library' }).click();
  await expect(page).toHaveURL(/\/library$/);
});
