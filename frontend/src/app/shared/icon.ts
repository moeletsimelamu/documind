import { ChangeDetectionStrategy, Component, input } from '@angular/core';

export type IconName =
  | 'upload'
  | 'search'
  | 'file'
  | 'trash'
  | 'download'
  | 'arrow-right'
  | 'alert'
  | 'check'
  | 'close'
  | 'question'
  | 'chevron-up'
  | 'chevron-down'
  | 'chevron-left'
  | 'chevron-right'
  | 'page';

/** A small fixed set of 16px line icons drawn with currentColor. Decorative unless labelled. */
@Component({
  selector: 'dm-icon',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { 'aria-hidden': 'true', class: 'dm-icon' },
  styles: `
    :host {
      display: inline-flex;
      flex: none;
    }
    svg {
      width: 16px;
      height: 16px;
    }
  `,
  template: `
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      focusable="false"
    >
      @switch (name()) {
        @case ('upload') {
          <path d="M12 16V4m0 0-5 5m5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
        }
        @case ('search') {
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-4-4" />
        }
        @case ('file') {
          <path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z" />
          <path d="M14 3v5h5M9 13h6M9 17h4" />
        }
        @case ('trash') {
          <path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />
        }
        @case ('download') {
          <path d="M12 4v12m0 0-5-5m5 5 5-5M4 20h16" />
        }
        @case ('arrow-right') {
          <path d="M5 12h14m-5-5 5 5-5 5" />
        }
        @case ('alert') {
          <path d="M12 4 2.5 20h19z" />
          <path d="M12 10v4M12 17.5v.5" />
        }
        @case ('check') {
          <path d="m5 12 5 5 9-10" />
        }
        @case ('close') {
          <path d="M6 6l12 12M18 6 6 18" />
        }
        @case ('question') {
          <circle cx="12" cy="12" r="9" />
          <path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6v.6M12 17.5v.5" />
        }
        @case ('chevron-up') {
          <path d="m6 15 6-6 6 6" />
        }
        @case ('chevron-down') {
          <path d="m6 9 6 6 6-6" />
        }
        @case ('chevron-left') {
          <path d="m15 6-6 6 6 6" />
        }
        @case ('chevron-right') {
          <path d="m9 6 6 6-6 6" />
        }
        @case ('page') {
          <rect x="5" y="3" width="14" height="18" rx="1" />
          <path d="M9 8h6M9 12h6M9 16h3" />
        }
      }
    </svg>
  `,
})
export class Icon {
  readonly name = input.required<IconName>();
}
