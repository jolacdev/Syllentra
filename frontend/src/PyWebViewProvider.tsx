import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ReactNode } from 'react';

import Icon from '@components/Icon';

import { createPyWebViewMock } from './mocks/mockPyWebView';

/** Wait for the native bridge; browser preview must be enabled explicitly. */
const PyWebViewProvider = ({ children }: { children: ReactNode }) => {
  const { t } = useTranslation();
  const [isReady, setIsReady] = useState(!!window.pywebview?.api);
  useEffect(() => {
    if (
      import.meta.env.DEV &&
      new URLSearchParams(location.search).has('preview')
    ) {
      createPyWebViewMock();
    }
    const ready = () => setIsReady(true);
    window.addEventListener('pywebviewready', ready);
    if (window.pywebview?.api) {
      ready();
    }
    return () => window.removeEventListener('pywebviewready', ready);
  }, []);
  if (isReady) {
    return children;
  }
  return (
    <main className="grid min-h-screen place-items-center p-8">
      <div className="max-w-md text-center">
        <Icon className="text-accent mx-auto mb-6 size-10" name="waveform" />
        <h1 className="text-xl font-semibold">{t('startup.connecting')}</h1>
        <p className="text-ink/70 mt-3 text-sm">
          {t('startup.desktopRequired')}
        </p>
        {import.meta.env.DEV && (
          <a
            className="text-accent mt-6 inline-block text-sm underline"
            href="?preview"
          >
            {t('startup.openPreview')}
          </a>
        )}
      </div>
    </main>
  );
};

export default PyWebViewProvider;
