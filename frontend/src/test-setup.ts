/**
 * Test environment setup. jsdom does not implement modal <dialog>; this minimal stand-in toggles
 * the `open` attribute so dialog-driven flows can be tested. Real behaviour (focus trapping, Esc,
 * inert background) is checked in the browser.
 */
if (typeof HTMLDialogElement !== 'undefined' && !HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.setAttribute('open', '');
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    this.removeAttribute('open');
    this.dispatchEvent(new Event('close'));
  };
}
