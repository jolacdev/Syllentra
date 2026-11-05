import { useTranslation } from 'react-i18next';

import Button from '@components/Button';
import { formatDuration } from '@utils/formatDuration';
import { formatSizeUnit } from '@utils/formatSizeUnit';
import type { MediaItem } from 'types/pywebview/pywebview-api';

import { useTranscript } from './useTranscript';

type ResultInspectorProps = {
  item: MediaItem | null;
  onCopy: (text: string) => void;
  onOpen: (id: string, reveal: boolean) => void;
  onExpand?: () => void;
};

/** Display source metadata, durable output outcomes, and a read-only session transcript. */
const ResultInspector = ({
  item,
  onCopy,
  onExpand = undefined,
  onOpen,
}: ResultInspectorProps) => {
  const { t } = useTranslation();
  const { error, navigate, offset, page, text } = useTranscript(item);
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
  return (
    <section
      aria-label={t('batch.fileDetails')}
      className="flex min-h-64 flex-1 flex-col"
    >
      <header className="shrink-0 px-5 pt-5 pb-4">
        <p className="text-ink/65 text-[10px] font-semibold tracking-widest uppercase">
          {t('batch.fileDetails')}
        </p>
        <h2 className="mt-2 truncate text-sm font-semibold" title={item.path}>
          {item.name}
        </h2>
        <p className="text-ink/65 mt-1 text-xs">
          {formatSizeUnit(item.size)} · {item.extension.toUpperCase().slice(1)}
        </p>
        {page && (
          <p className="text-ink/65 mt-2 text-xs tabular-nums">
            {t('batch.fileTiming', {
              duration: formatDuration(page.duration),
              processing: formatDuration(page.processingSeconds),
            })}
          </p>
        )}
        <details className="text-ink/65 mt-2 text-xs">
          <summary className="cursor-pointer">
            {t('batch.sourceLocation')}
          </summary>
          <p className="mt-2 break-all">{item.path}</p>
        </details>
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
      </header>
      <div className="border-ink/10 flex items-center justify-between gap-3 border-y px-5 py-2">
        <h3 className="text-xs font-semibold">{t('batch.previewTitle')}</h3>
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
          className="min-h-8 px-1.5 py-1"
          disabled={!text}
          icon="content-copy"
          variant="ghost"
          onClick={() => onCopy(text)}
        />
      </div>
      <div className="min-h-32 flex-1 overflow-y-auto px-5 py-4">
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
          <ol className="space-y-4">
            {page.segments.map((segment) => (
              <li key={segment.id}>
                <span className="text-ink/65 font-mono text-[10px] tabular-nums">
                  {Math.floor(segment.start / 60)}:
                  {String(Math.floor(segment.start % 60)).padStart(2, '0')}
                </span>
                <p className="mt-1 text-sm leading-6 break-words whitespace-pre-wrap">
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
    </section>
  );
};

export default ResultInspector;
