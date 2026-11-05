// NOTE: https://vitest.dev/guide/extending-matchers
import * as matchers from '@testing-library/jest-dom/matchers';
import { expect } from 'vitest';
import type { TestingLibraryMatchers } from '@testing-library/jest-dom/matchers';

// NOTE: Extends TypeScript `Assertion` interface used in Vitest's `expect` with the Jest-DOM matchers.
declare module 'vitest' {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  interface Assertion<T = any>
    extends jest.Matchers<void, T>,
      TestingLibraryMatchers<T, void> {}
}

// NOTE: Extends the `expect` function from Vitest to add the matchers of Jest-DOM. Allowing the use of matchers like `.toBeInTheDocument()`.
expect.extend(matchers);

// JSDOM has no native dialog implementation; browser focus trapping is outside DOM unit tests.
/** Represent native modal visibility for confirmation tests. */
HTMLDialogElement.prototype.showModal = function showModal() {
  this.open = true;
};

/** Represent native dialog dismissal without simulating browser focus behavior. */
HTMLDialogElement.prototype.close = function close() {
  this.open = false;
};

/** Model a stable media query so feedback can honor reduced-motion detection in JSDOM. */
const matchMedia = (query: string): MediaQueryList => ({
  matches: false,
  media: query,
  onchange: null,
  /** Expose the standard event interface for consumers that subscribe to preference changes. */
  addEventListener: () => {},
  /** Retain the deprecated static-listener surface without simulating viewport changes. */
  addListener: () => {},
  /** Report that a static test query dispatches no browser events. */
  dispatchEvent: () => false,
  /** Keep unsubscribe safe for a static query during component cleanup. */
  removeEventListener: () => {},
  /** Remove no listeners because this query remains static during a unit test. */
  removeListener: () => {},
});
Object.defineProperty(window, 'matchMedia', {
  configurable: true,
  value: matchMedia,
  writable: true,
});
