import { useTranslation } from 'react-i18next';

import type { ModelState } from 'types/pywebview/pywebview-api';

import ElapsedTime from './ElapsedTime';

/** Show preparation status and measured elapsed time while native model setup runs. */
const ModelSetupProgress = ({ model }: { model: ModelState }) => {
  const { t } = useTranslation();
  return (
    <div className="mt-2 max-w-lg space-y-2">
      <p className="text-xs" role="status">
        {t(
          model.status === 'cancelling'
            ? 'batch.setupCancelling'
            : 'batch.setupWorking',
        )}
      </p>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <ElapsedTime isRunning seconds={model.elapsedSeconds} />
        <span className="text-ink/65 text-xs">
          {t('batch.setupProgressHint')}
        </span>
      </div>
    </div>
  );
};

export default ModelSetupProgress;
