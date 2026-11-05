import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import en from './locales/en.json';
import es from './locales/es.json';

const language = navigator.language.startsWith('es') ? 'es-ES' : 'en';
document.documentElement.lang = language;

// Scoped camelCase keys keep wording independent from component logic.
i18n
  .use(initReactI18next)
  .init({
    fallbackLng: 'en',
    interpolation: { escapeValue: false },
    lng: language,
    nsSeparator: false,
    resources: { en: { translation: en }, 'es-ES': { translation: es } },
    supportedLngs: ['en', 'es-ES'],
  })
  .catch((error: unknown) =>
    // eslint-disable-next-line no-console -- Startup failures occur before UI feedback is available.
    console.error('Could not initialize translations', error),
  );

export default i18n;
