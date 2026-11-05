import { useEffect } from 'react';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';

import { Notifications } from '@components/Feedback';
import { useTranscription } from '@features/transcription/useTranscription';
import BatchWorkspaceScreen from '@screens/BatchWorkspaceScreen';

/** Apply persisted interface preferences and compose the single backend-owned batch workspace. */
const App = () => {
  const { i18n, t } = useTranslation();
  const controller = useTranscription();
  const { error, reportError, state } = controller;
  const theme = state?.preferences.theme ?? 'system';
  const language = state?.preferences.interfaceLanguage;
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  useEffect(() => {
    if (!language) {
      return;
    }
    const next =
      language === 'system'
        ? navigator.language.startsWith('es')
          ? 'es-ES'
          : 'en'
        : language;
    document.documentElement.lang = next;
    i18n.changeLanguage(next).catch(reportError);
  }, [i18n, language, reportError]);
  useEffect(() => {
    if (error) {
      toast.error(
        <div>
          <p className="font-medium">{t(`batch.commandError.${error.code}`)}</p>
          <details className="mt-2 text-xs">
            <summary className="cursor-pointer">
              {t('errors.technicalDetails')}
            </summary>
            <p className="mt-2 max-h-36 overflow-auto break-words whitespace-pre-wrap">
              {error.details}
            </p>
          </details>
        </div>,
        { id: 'command-error' },
      );
    } else {
      toast.dismiss('command-error');
    }
  }, [error, t]);
  return (
    <>
      <Notifications />
      <BatchWorkspaceScreen controller={controller} />
    </>
  );
};

export default App;
