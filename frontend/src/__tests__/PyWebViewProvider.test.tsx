import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import i18n from '../i18n/i18n';
import { createPyWebViewMock } from '../mocks/mockPyWebView';
import PyWebViewProvider from '../PyWebViewProvider';

/** Model pywebview's partial installation without claiming the complete runtime contract. */
const installBridge = (bridge: unknown) => {
  Object.defineProperty(window, 'pywebview', {
    configurable: true,
    value: bridge,
    writable: true,
  });
};

beforeEach(async () => {
  window.history.replaceState({}, '', '/');
  installBridge(undefined);
  await i18n.changeLanguage('en');
});

afterEach(() => {
  cleanup();
  installBridge(undefined);
});

describe('native bridge startup', () => {
  it.each([undefined, { api: {} }, { api: { get_state: () => {} } }])(
    'keeps the connecting screen until commands and state exist (%j)',
    async (bridge) => {
      installBridge(bridge);
      render(
        <PyWebViewProvider>
          <p>Desktop workspace</p>
        </PyWebViewProvider>,
      );
      expect(screen.queryByText('Desktop workspace')).not.toBeInTheDocument();
      await act(() => window.dispatchEvent(new Event('pywebviewready')));
      expect(screen.queryByText('Desktop workspace')).not.toBeInTheDocument();
      await act(() => {
        installBridge(undefined);
        createPyWebViewMock();
        window.dispatchEvent(new Event('pywebviewready'));
      });
      expect(screen.getByText('Desktop workspace')).toBeInTheDocument();
    },
  );

  it('accepts a bridge initialized before React mounts', () => {
    createPyWebViewMock();
    render(
      <PyWebViewProvider>
        <p>Desktop workspace</p>
      </PyWebViewProvider>,
    );
    expect(screen.getByText('Desktop workspace')).toBeInTheDocument();
  });
});
