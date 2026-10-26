import { Injectable } from '@angular/core';
import type { PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist';
import type { TextItem } from 'pdfjs-dist/types/src/display/api';

/** An area of the rendered page, in CSS pixels from its top-left corner. */
export interface PageBox {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface RenderedPage {
  pageCount: number;
  width: number;
  height: number;
  /** Where the given passage's text appears on the page; empty if it could not be located. */
  passageBoxes: PageBox[];
}

/** The pieces of a page's text layer that are needed to locate a passage. */
export interface PageTextItem {
  str: string;
}

/** Letters and digits only, lower case: survives the layout clean-up and pdf.js's own splitting. */
function compact(text: string): string {
  return text
    .normalize('NFKC')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, '');
}

/** A text item this long that occurs in the passage is taken as part of it on its own. */
const ANCHOR_CHARS = 12;
/** Shorter items count only next to an anchor, so that "the" or "page" is not outlined alone. */
const MIN_CHARS = 3;
const NEIGHBOURHOOD = 2;

/**
 * Indexes of the text items that belong to a passage. pdf.js returns a page's text as runs (a line
 * or part of one); DocuMind stores cleaned-up text. Both are compared as letters and digits only.
 * Exported for tests.
 */
export function itemsInPassage(items: readonly PageTextItem[], passage: string): number[] {
  const target = compact(passage);
  if (!target) {
    return [];
  }
  const keys = items.map((item) => compact(item.str));
  const inPassage = keys.map((key) => key.length >= MIN_CHARS && target.includes(key));
  const anchors = keys.map((key, i) => inPassage[i] && key.length >= ANCHOR_CHARS);
  const chosen: number[] = [];
  keys.forEach((_, i) => {
    if (!inPassage[i]) {
      return;
    }
    const near = anchors
      .slice(Math.max(0, i - NEIGHBOURHOOD), i + NEIGHBOURHOOD + 1)
      .some((anchor) => anchor);
    if (near) {
      chosen.push(i);
    }
  });
  return chosen;
}

const PDFJS_BASE = 'pdfjs/';

/**
 * Renders pages of an uploaded PDF with pdf.js, loaded only when first needed. Documents run in
 * pdf.js's worker; scripts, forms and XFA in a PDF are never executed (pdf.js runs those only in its
 * full viewer, which is not used), and nothing is loaded from outside this site.
 */
@Injectable({ providedIn: 'root' })
export class PdfPageRenderer {
  private library: Promise<typeof import('pdfjs-dist')> | null = null;
  private readonly documents = new Map<string, Promise<PDFDocumentProxy>>();

  private pdfjs(): Promise<typeof import('pdfjs-dist')> {
    this.library ??= import('pdfjs-dist').then((pdfjs) => {
      pdfjs.GlobalWorkerOptions.workerSrc = this.asset('pdf.worker.min.mjs');
      return pdfjs;
    });
    return this.library;
  }

  private asset(path: string): string {
    return new URL(PDFJS_BASE + path, document.baseURI).href;
  }

  private open(fileUrl: string): Promise<PDFDocumentProxy> {
    let loading = this.documents.get(fileUrl);
    if (!loading) {
      loading = Promise.all([
        this.pdfjs(),
        fetch(fileUrl, { credentials: 'same-origin' }).then((response) => {
          if (!response.ok) {
            throw new Error(`The original file could not be loaded (${response.status}).`);
          }
          return response.arrayBuffer();
        }),
      ]).then(
        ([pdfjs, data]) =>
          pdfjs.getDocument({
            data: new Uint8Array(data),
            enableXfa: false,
            standardFontDataUrl: this.asset('standard_fonts/'),
            cMapUrl: this.asset('cmaps/'),
            cMapPacked: true,
            iccUrl: this.asset('iccs/'),
            wasmUrl: this.asset('wasm/'),
          }).promise,
      );
      loading.catch(() => this.documents.delete(fileUrl)); // allow a retry after a failure
      this.documents.set(fileUrl, loading);
    }
    return loading;
  }

  /** Draws one page into the canvas at the given CSS width and locates the passage on it. */
  async render(
    fileUrl: string,
    pageNumber: number,
    canvas: HTMLCanvasElement,
    cssWidth: number,
    passage: string | null,
  ): Promise<RenderedPage> {
    const pdf = await this.open(fileUrl);
    const page: PDFPageProxy = await pdf.getPage(pageNumber);
    const unscaled = page.getViewport({ scale: 1 });
    const viewport = page.getViewport({ scale: cssWidth / unscaled.width });
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.floor(viewport.width * ratio);
    canvas.height = Math.floor(viewport.height * ratio);
    canvas.style.width = `${viewport.width}px`;
    canvas.style.height = `${viewport.height}px`;
    await page.render({
      canvas,
      viewport,
      transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0],
    }).promise;

    let passageBoxes: PageBox[] = [];
    if (passage) {
      const { Util } = await this.pdfjs();
      const content = await page.getTextContent();
      const items = content.items.filter((item): item is TextItem => 'str' in item);
      passageBoxes = itemsInPassage(items, passage).map((index) => {
        const item = items[index];
        const [, , c, d, x, y] = Util.transform(viewport.transform, item.transform) as number[];
        const height = Math.hypot(c, d);
        return {
          left: x,
          top: y - height,
          width: item.width * viewport.scale,
          height: height * 1.2,
        };
      });
    }
    return {
      pageCount: pdf.numPages,
      width: viewport.width,
      height: viewport.height,
      passageBoxes,
    };
  }
}
