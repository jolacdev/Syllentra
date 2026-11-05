import { useTranslation } from 'react-i18next';

import { formatDuration } from '@utils/formatDuration';
import type { BatchState } from 'types/pywebview/pywebview-api';

/** Keep measured batch time visible after completion, cancellation, or failure. */
const BatchSummary = ({ batch }: { batch: BatchState }) => {
  const { t } = useTranslation();
  return (
    <div
      aria-label={t('batch.summaryTitle')}
      className="mt-2 text-xs tabular-nums"
      role="group"
    >
      {t('batch.summaryElapsed', {
        time: formatDuration(batch.elapsedSeconds),
      })}
    </div>
  );
};

export default BatchSummary;
