import { useEffect } from 'react';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import type { MouseEvent } from 'react';

import Button from '@components/Button';
import { Notifications } from '@components/Feedback';
import { cn } from '@utils/cn';
import { formatDuration } from '@utils/formatDuration';
import { formatSizeUnit } from '@utils/formatSizeUnit';
import type { MediaItem } from 'types/pywebview/pywebview-api';

import AudioTrackPicker from './AudioTrackPicker';
import { useTranscript } from './useTranscript';

const expandedToasterId = 'expanded-transcript';

type ResultInspectorProps = {
  item: MediaItem | null;
  isEditingDisabled: boolean;
  isExpanded?: boolean;
  onCopyError: (reason: unknown) => void;
  onOpen: (id: string, reveal: boolean) => void;
  onSelectTrack: (index: null | number) => void;
  onExpand?: () => void;
};

/** Display source metadata, durable output outcomes, and a read-only session transcript. */
const ResultInspector = ({
  item,
  onCopyError,
  onExpand = undefined,
  onOpen,
  onSelectTrack,
  isEditingDisabled,
  isExpanded = false,
}: ResultInspectorProps) => {
  const { t } = useTranslation();
  const { error, navigate, offset, page, text } = useTranscript(item);
  useEffect(() => {
    if (isExpanded) {
      return () => toast.removeAll(expandedToasterId);
    }
  }, [isExpanded]);

  if (!item) {
    return (
      <section className="text-ink/65 flex min-h-0 flex-1 flex-col justify-center px-6 py-5">
        <p className="text-sm font-medium">{t('batch.previewTitle')}</p>
        <p className="mt-2 max-w-64 text-xs leading-5">
          {t('batch.previewEmpty')}
        </p>
      </section>
    );
  }
  /** Show clipboard feedback in the dialog's own layer when expanded. */
  const copy = (event: MouseEvent<HTMLButtonElement>) => {
    const button = event.currentTarget;
    const toasterId = isExpanded ? expandedToasterId : undefined;
    const write =
      navigator.clipboard?.writeText(text) ??
      Promise.reject(new Error(t('transcript.copyFailed')));
    write
      .then(() => {
        if (!isExpanded || button.isConnected) {
          toast.success(t('transcript.copiedNotice'), { toasterId });
        }
      })
      .catch((reason: unknown) => {
        if (isExpanded) {
          if (button.isConnected) {
            toast.error(t('transcript.copyFailed'), { toasterId });
          }
        } else {
          onCopyError(reason);
        }
      });
  };

  const timing = page
    ? t('batch.fileTiming', {
        duration: formatDuration(page.duration),
        processing: formatDuration(page.processingSeconds),
      })
    : null;
  const details = (
    <div
      className={cn(
        'shrink-0 px-5 pt-5 pb-4',
        isExpanded &&
          'border-ink/10 bg-canvas/60 max-h-[30%] overflow-y-auto border-t md:max-h-none md:w-72 md:border-t-0 md:border-l',
      )}
    >
      {isExpanded ? (
        <h3 className="text-sm font-semibold">{t('batch.fileDetails')}</h3>
      ) : (
        <>
          <p className="text-ink/65 text-[10px] font-semibold tracking-widest uppercase">
            {t('batch.fileDetails')}
          </p>
          <h2 className="mt-2 truncate text-sm font-semibold" title={item.path}>
            {item.name}
          </h2>
        </>
      )}
      <p className="text-ink/65 mt-1 text-xs">
        {formatSizeUnit(item.size)} · {item.extension.toUpperCase().slice(1)}
      </p>
      {!isExpanded && timing && (
        <p className="text-ink/65 mt-2 text-xs tabular-nums">{timing}</p>
      )}
      <details className="text-ink/65 mt-2 text-xs">
        <summary className="cursor-pointer">
          {t('batch.sourceLocation')}
        </summary>
        <p className="mt-2 break-all">{item.path}</p>
      </details>
      <AudioTrackPicker
        isDisabled={isEditingDisabled}
        item={item}
        onSelect={onSelectTrack}
      />
      {item.error && (
        <div
          className="border-danger/20 bg-danger/5 text-danger mt-4 rounded-lg border p-3 text-xs"
          role="status"
        >
          <p className="font-medium">
            {t(`batch.failure.${item.errorStage ?? 'inference'}`)}
          </p>
          <details className="mt-2 leading-5">
            <summary className="cursor-pointer">
              {t('errors.technicalDetails')}
            </summary>
            <p className="mt-1 break-words">{item.error}</p>
          </details>
          {item.errorStage === 'export' && (
            <p className="mt-2 leading-5">{t('batch.retryExportHint')}</p>
          )}
        </div>
      )}
      {item.outputs.length > 0 && (
        <div className="mt-4 space-y-2">
          <h3 className="text-ink/65 text-xs">{t('batch.outputFiles')}</h3>
          {item.outputs.map((output) => (
            <div
              key={output.id}
              className="border-ink/10 flex items-center gap-2 rounded-lg border px-2.5 py-1.5"
            >
              <span className="text-xs font-semibold">
                {output.format.toUpperCase()}
              </span>
              <span
                className="text-ink/65 min-w-0 flex-1 truncate text-xs"
                title={output.error ?? output.path}
              >
                {t(`batch.outputStatus.${output.status}`)}
              </span>
              {output.status === 'written' && (
                <>
                  <Button
                    aria-label={t('batch.revealOutput', {
                      format: output.format.toUpperCase(),
                    })}
                    className="min-h-8 px-1.5 py-1"
                    icon="folder-outline"
                    title={output.path}
                    variant="ghost"
                    onClick={() => onOpen(output.id, true)}
                  />
                  <Button
                    aria-label={t('batch.openOutput', {
                      format: output.format.toUpperCase(),
                    })}
                    className="min-h-8 px-1.5 py-1"
                    icon="open-in-new"
                    variant="ghost"
                    onClick={() => onOpen(output.id, false)}
                  />
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
  const reader = (
    <>
      <div
        className={cn(
          'border-ink/10 flex shrink-0 items-center justify-between gap-3 px-5 py-2',
          isExpanded ? 'border-b' : 'border-y',
        )}
      >
        {isExpanded ? (
          <div className="min-w-0 flex-1">
            <h3 className="truncate text-sm font-semibold" title={item.name}>
              {item.name}
            </h3>
            {timing && (
              <p className="text-ink/65 mt-0.5 text-xs tabular-nums">
                {timing}
              </p>
            )}
          </div>
        ) : (
          <h3 className="text-xs font-semibold">{t('batch.previewTitle')}</h3>
        )}
        {onExpand && (
          <Button
            aria-label={t('batch.expandPreview')}
            className="ml-auto min-h-8 px-2 py-1"
            icon="open-in-new"
            title={t('batch.expandPreview')}
            variant="ghost"
            onClick={onExpand}
          >
            {t('batch.expand')}
          </Button>
        )}
        <Button
          aria-label={t('transcript.copyText')}
          className={
            isExpanded ? 'size-9 min-h-9 shrink-0 p-0' : 'min-h-8 px-1.5 py-1'
          }
          disabled={!text}
          icon="content-copy"
          title={t('transcript.copyText')}
          variant="ghost"
          onClick={copy}
        />
      </div>
      <div
        aria-label={isExpanded ? t('batch.previewTitle') : undefined}
        className={cn(
          'flex-1 overflow-y-auto px-5 py-4',
          isExpanded
            ? 'min-h-0 overscroll-contain focus-visible:-outline-offset-4 sm:px-8'
            : 'min-h-32',
        )}
        role={isExpanded ? 'region' : undefined}
        tabIndex={isExpanded ? 0 : undefined}
      >
        {error ? (
          <p className="text-danger text-xs" role="alert">
            {t('batch.previewFailed')}
            <span className="mt-2 block">{error}</span>
          </p>
        ) : !item.resultId ? (
          <p className="text-ink/65 text-xs leading-6">
            {t('batch.previewPending')}
          </p>
        ) : !page ? (
          <p className="text-ink/65 text-xs" role="status">
            {t('batch.loadingPreview')}
          </p>
        ) : item.noSpeech ? (
          <p className="text-ink/65 text-sm leading-6">
            {t('transcript.noSpeechHint')}
          </p>
        ) : (
          <ol
            className={
              isExpanded
                ? 'divide-ink/10 mx-auto w-full max-w-[78ch] divide-y'
                : 'space-y-4'
            }
          >
            {page.segments.map((segment) => (
              <li
                key={segment.id}
                className={
                  isExpanded
                    ? 'grid grid-cols-[3rem_minmax(0,1fr)] gap-2 py-3 sm:grid-cols-[4rem_minmax(0,1fr)]'
                    : undefined
                }
              >
                <span
                  className={cn(
                    'text-ink/65 font-mono tabular-nums',
                    isExpanded ? 'pt-1 text-xs' : 'text-[10px]',
                  )}
                >
                  {Math.floor(segment.start / 60)}:
                  {String(Math.floor(segment.start % 60)).padStart(2, '0')}
                </span>
                <p
                  className={cn(
                    'break-words whitespace-pre-wrap',
                    isExpanded
                      ? 'text-base leading-7'
                      : 'mt-1 text-sm leading-6',
                  )}
                >
                  {segment.text}
                </p>
              </li>
            ))}
          </ol>
        )}
      </div>
      {page && page.totalSegments > 200 && (
        <footer className="border-ink/10 flex shrink-0 items-center justify-between border-t px-5 py-2">
          <Button
            disabled={offset === 0}
            variant="ghost"
            onClick={() => navigate(Math.max(0, offset - 200))}
          >
            {t('batch.previous')}
          </Button>
          <span className="text-ink/65 text-xs">
            {offset + 1}–{Math.min(offset + 200, page.totalSegments)} /{' '}
            {page.totalSegments}
          </span>
          <Button
            disabled={offset + 200 >= page.totalSegments}
            variant="ghost"
            onClick={() => navigate(offset + 200)}
          >
            {t('batch.next')}
          </Button>
        </footer>
      )}
    </>
  );
  return (
    <section
      aria-label={isExpanded ? undefined : t('batch.fileDetails')}
      className={cn(
        'flex flex-1 flex-col',
        isExpanded ? 'relative min-h-0 overflow-hidden' : 'min-h-64',
      )}
    >
      {isExpanded ? (
        <>
          <div className="flex min-h-0 flex-1 flex-col md:flex-row">
            <div className="flex min-h-0 min-w-0 flex-1 flex-col">{reader}</div>
            {details}
          </div>
          <Notifications
            containerStyle={{ position: 'absolute' }}
            toasterId={expandedToasterId}
          />
        </>
      ) : (
        <>
          {details}
          {reader}
        </>
      )}
    </section>
  );
};

export default ResultInspector;
