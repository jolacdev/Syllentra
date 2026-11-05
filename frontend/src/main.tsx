import React from 'react';
import ReactDOM from 'react-dom/client';

import App from './App';
import PyWebViewProvider from './PyWebViewProvider';
import type { PyWebViewApiType } from './types/pywebview/pywebview-api';
import type { PyWebViewState } from './types/pywebview/pywebview-state';

import './i18n/i18n';

import './index.css';

declare global {
  interface Window {
    pywebview: { api: PyWebViewApiType; state: PyWebViewState };
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <PyWebViewProvider>
      <App />
    </PyWebViewProvider>
  </React.StrictMode>,
);
