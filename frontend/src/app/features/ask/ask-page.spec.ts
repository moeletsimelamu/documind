import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { makeAskResponse, makeConfig, makeHit } from '../../../testing/fixtures';
import { ConfigService } from '../../core/config.service';
import { AskPage } from './ask-page';

describe('AskPage', () => {
  let fixture: ComponentFixture<AskPage>;
  let http: HttpTestingController;
  let page: HTMLElement;

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [AskPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(AskPage);
    page = fixture.nativeElement as HTMLElement;
    await fixture.whenStable();
  });

  const field = () => page.querySelector<HTMLTextAreaElement>('#question')!;
  const text = () => page.textContent?.replace(/\s+/g, ' ') ?? '';

  async function typeQuestion(value: string): Promise<void> {
    field().value = value;
    field().dispatchEvent(new Event('input'));
    await fixture.whenStable();
  }

  function pressEnter(shiftKey = false): KeyboardEvent {
    const event = new KeyboardEvent('keydown', { key: 'Enter', shiftKey, cancelable: true });
    field().dispatchEvent(event);
    return event;
  }

  it('explains that AI answers are off and the thread stays in this tab', () => {
    expect(text()).toContain('AI answers are off on this server');
    expect(text()).toContain('stay in this browser tab only');
  });

  it('asks with Enter, clears the field at once, and shows the passages as numbered sources', async () => {
    await typeQuestion('Which supplier was late?');

    const event = pressEnter();
    expect(event.defaultPrevented).toBe(true);
    expect(field().value).toBe(''); // cleared even before the next render
    const request = http.expectOne('/api/ask');
    expect(request.request.body).toEqual({
      question: 'Which supplier was late?',
      document_ids: null,
    });
    await fixture.whenStable();
    expect(text()).toContain('Looking for relevant passages');

    request.flush(
      makeAskResponse({
        passages: [makeHit(), makeHit({ chunk_id: 12, document_name: 'notes.txt' })],
      }),
    );
    await fixture.whenStable();

    expect(page.querySelector('.question')?.textContent).toBe('Which supplier was late?');
    expect(text()).toContain('Relevant passages');
    expect(Array.from(page.querySelectorAll('.label')).map((l) => l.textContent)).toEqual([
      'S1',
      'S2',
    ]);
    // Passages are presented as sources, never as a generated answer.
    expect(page.querySelector('.response-label')?.textContent).toContain('Relevant passages');
    expect(text()).not.toContain('Answer ·');
  });

  it('Shift+Enter adds a new line instead of asking', async () => {
    await typeQuestion('First line');

    expect(pressEnter(true).defaultPrevented).toBe(false);
    http.expectNone('/api/ask');
  });

  it('says plainly when the documents do not contain an answer', async () => {
    await typeQuestion('Who won the rugby final?');
    pressEnter();
    http.expectOne('/api/ask').flush(
      makeAskResponse({
        mode: 'insufficient_evidence',
        searched_for: ['won', 'rugby', 'final'],
        passages: [],
      }),
    );
    await fixture.whenStable();

    expect(text()).toContain('Not enough in your documents to answer this');
    const terms = Array.from(page.querySelectorAll('.insufficient q')).map((q) => q.textContent);
    expect(terms).toEqual(['won', 'rugby', 'final']);
    expect(text()).toContain('final. Try the words'); // no stray space before the full stop
    expect(page.querySelector('dm-passage-card')).toBeNull();
  });

  it('does not send a second question while one is in progress', async () => {
    await typeQuestion('First question');
    pressEnter();
    await typeQuestion('Second question');

    pressEnter();

    expect(http.match('/api/ask')).toHaveLength(1);
    expect(page.querySelector<HTMLButtonElement>('button[type="submit"]')!.disabled).toBe(true);
  });

  it('shows the error with a retry that sends the same question again', async () => {
    await typeQuestion('What is the budget?');
    pressEnter();
    http.expectOne('/api/ask').flush(null, { status: 0, statusText: 'Unknown Error' });
    await fixture.whenStable();
    expect(page.querySelector('[role="alert"]')?.textContent).toContain(
      "Can't reach the DocuMind server",
    );

    page.querySelector<HTMLButtonElement>('[role="alert"] button')!.click();

    const retry = http.expectOne('/api/ask');
    expect(retry.request.body.question).toBe('What is the budget?');
    retry.flush(makeAskResponse());
    await fixture.whenStable();
    expect(page.querySelectorAll('.entry')).toHaveLength(1);
    expect(text()).toContain('Relevant passages');
  });

  it('refuses questions over the length limit', async () => {
    await typeQuestion('x'.repeat(1001));

    pressEnter();

    http.expectNone('/api/ask');
    expect(field().getAttribute('aria-invalid')).toBe('true');
  });

  async function askAndAnswer(response: ReturnType<typeof makeAskResponse>): Promise<void> {
    await typeQuestion('What budget was approved?');
    pressEnter();
    http.expectOne('/api/ask').flush(response);
    await fixture.whenStable();
  }

  it('tells the user when AI answers are on and what is sent to the provider', async () => {
    TestBed.inject(ConfigService).config.set(makeConfig({ llm_enabled: true, llm_model: 'gpt-x' }));
    await fixture.whenStable();

    expect(text()).toContain('AI answers are on (gpt-x)');
    expect(text()).toContain('sent to the AI provider configured on this server');
  });

  it('says the model is writing while an AI answer is on its way', async () => {
    TestBed.inject(ConfigService).config.set(makeConfig({ llm_enabled: true, llm_model: 'gpt-x' }));
    await typeQuestion('What budget was approved?');
    pressEnter();
    await fixture.whenStable();

    expect(text()).toContain('Finding passages and asking gpt-x for an answer');
    http.expectOne('/api/ask');
  });

  it('offers the cited sources after an answer that has no markers in its text', async () => {
    await askAndAnswer(
      makeAskResponse({
        mode: 'generated',
        answer: 'The budget is R4.5 million.',
        cited: ['S2'],
        model: 'small-model',
        passages: [
          makeHit({ chunk_id: 1, document_name: 'notes.txt' }),
          makeHit({ chunk_id: 2, document_name: 'minutes.pdf' }),
        ],
      }),
    );

    const chips = Array.from(page.querySelectorAll<HTMLButtonElement>('.answer-sources .marker'));
    expect(chips.map((chip) => chip.textContent)).toEqual(['S2']);
    expect(page.querySelector('.answer-sources')?.textContent).toContain('Based on');

    chips[0].click();
    await fixture.whenStable();

    expect(page.querySelectorAll('.sources-panel li')[1].classList).toContain('selected');
  });

  it('shows a generated answer with markers that open the cited sources', async () => {
    await askAndAnswer(
      makeAskResponse({
        mode: 'generated',
        answer: 'The budget is R4.5 million [S2].',
        cited: ['S2'],
        model: 'gpt-x',
        passages: [
          makeHit({ chunk_id: 1, document_name: 'notes.txt' }),
          makeHit({
            chunk_id: 2,
            document_name: 'minutes.pdf',
            excerpt: 'Budget of R4.5 million.',
          }),
        ],
      }),
    );

    expect(page.querySelector('.response-label')?.textContent).toContain('generated by gpt-x');
    expect(page.querySelector('.answer-text')?.textContent?.replace(/\s+/g, ' ').trim()).toBe(
      'The budget is R4.5 million S2.',
    );
    expect(page.querySelector('.caution')?.textContent).toContain('Generated text can be wrong');
    const sources = Array.from(page.querySelectorAll('.sources-panel li'));
    expect(sources).toHaveLength(2);
    expect(sources[0].classList).toContain('uncited');
    expect(sources[0].textContent).toContain('Retrieved but not cited');
    expect(sources[1].classList).not.toContain('uncited');

    page.querySelector<HTMLButtonElement>('.marker')!.click();
    await fixture.whenStable();

    expect(sources[1].classList).toContain('selected');
    expect(document.activeElement).toBe(sources[1]);
    expect(page.querySelector('.marker')!.classList).toContain('active');
  });

  it('falls back to passages with an explanation when the provider fails', async () => {
    await askAndAnswer(
      makeAskResponse({
        generation_error: {
          code: 'provider_timeout',
          message: 'The AI provider did not respond in time.',
        },
        model: 'gpt-x',
      }),
    );

    const banner = page.querySelector('.banner-warning')!;
    expect(banner.textContent).toContain('No AI answer this time.');
    expect(banner.textContent).toContain('did not respond in time');
    expect(page.querySelector('.response-label')?.textContent).toContain('Relevant passages');
    expect(page.querySelector('.answer')).toBeNull();
  });

  it('shows the closest passages when the model finds the evidence insufficient', async () => {
    await askAndAnswer(makeAskResponse({ mode: 'insufficient_evidence', model: 'gpt-x' }));

    expect(text()).toContain('Not enough in your documents to answer this');
    expect(text()).toContain('do not answer this question');
    expect(page.querySelector('.closest-heading')?.textContent).toContain('Closest passages');
    expect(page.querySelectorAll('dm-passage-card')).toHaveLength(1);
    expect(page.querySelector('.answer')).toBeNull();
  });
});
