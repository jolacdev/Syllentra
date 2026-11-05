import { useId } from 'react';
import { useTranslation } from 'react-i18next';

import type { BatchState, MediaItem } from 'types/pywebview/pywebview-api';

import ElapsedTime from './ElapsedTime';

type BatchProgressProps = {
  batch: BatchState;
  item: null | Pick<MediaItem, 'name' | 'path'>;
};

/** Separate current-recording transcription from overall queue completion with exactly two indicators. */
const BatchProgress = ({ batch, item }: BatchProgressProps) => {
  const { t } = useTranslation();
  const fileLabel = useId();
  const batchLabel = useId();
  const done = batch.completed + batch.failed + batch.skipped + batch.cancelled;
  const total = Math.max(1, batch.total);
  // Saving outputs follows completed transcription but does not finish the batch item yet.
  const fileProgress = !item
    ? undefined
    : batch.phase === 'exporting'
      ? 100
      : batch.phase === 'transcribing'
        ? (batch.progress ?? undefined)
        : undefined;

  return (
    <div className="grid min-w-0 gap-4 sm:grid-cols-2">
      <section aria-labelledby={fileLabel} className="min-w-0">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-xs font-semibold" id={fileLabel}>
            {t('batch.fileProgress')}
          </h2>
          {fileProgress !== undefined && (
            <span className="text-ink/65 text-xs tabular-nums">
              {Math.floor(fileProgress)}%
            </span>
          )}
        </div>
        <progress
          aria-labelledby={fileLabel}
          className="mt-2 block h-1.5 w-full"
          max={100}
          title={t('batch.fileProgressHint')}
          value={fileProgress}
        />
        <p className="mt-1.5 truncate text-xs" title={item?.path}>
          {item?.name ?? t('batch.waitingFile')}
        </p>
        {item && (
          <p className="text-ink/65 mt-0.5 text-[11px]" role="status">
            {t(`batch.phase.${batch.phase || 'preparing'}`)}
          </p>
        )}
      </section>
      <section
        aria-labelledby={batchLabel}
        className="border-ink/10 min-w-0 sm:border-l sm:pl-4"
      >
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-xs font-semibold" id={batchLabel}>
            {t('batch.batchProgress')}
          </h2>
          <span className="text-ink/65 text-xs tabular-nums">
            {Math.floor((done / total) * 100)}%
          </span>
        </div>
        <progress
          aria-labelledby={batchLabel}
          aria-valuetext={t('batch.batchFinishedCount', {
            done,
            total: batch.total,
          })}
          className="mt-2 block h-1.5 w-full"
          max={total}
          title={t('batch.batchProgressHint')}
          value={done}
        />
        <p className="text-ink/65 mt-1.5 text-xs tabular-nums">
          {t('batch.batchFinishedCount', { done, total: batch.total })}
        </p>
        <ElapsedTime
          key={batch.id}
          isRunning={batch.status === 'running' || batch.status === 'stopping'}
          seconds={batch.elapsedSeconds}
        />
      </section>
    </div>
  );
};

export default BatchProgress;
