import { useState } from 'react';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';

import Button from '@components/Button';
import Checkbox from '@components/Checkbox';
import Icon from '@components/Icon';
import Modal from '@components/Modal';
import Select from '@components/Select';
import BatchProgress from '@features/transcription/BatchProgress';
import BatchSummary from '@features/transcription/BatchSummary';
import ConflictReviewDialog from '@features/transcription/ConflictReviewDialog';
import ExportSettingsPanel from '@features/transcription/ExportSettingsPanel';
import MediaTree from '@features/transcription/MediaTree';
import ModelSetupProgress from '@features/transcription/ModelSetupProgress';
import ResultInspector from '@features/transcription/ResultInspector';
import { selectionState } from '@features/transcription/tree';
import { cn } from '@utils/cn';
import type { useTranscription } from '@features/transcription/useTranscription';
import type { InterfacePreferences } from 'types/pywebview/pywebview-api';

import { useNativeDrop } from '../features/transcription/useNativeDrop';

type Controller = ReturnType<typeof useTranscription>;
type BatchWorkspaceScreenProps = { controller: Controller };
const themeModes: InterfacePreferences['theme'][] = ['system', 'light', 'dark'];

/** Compose one persistent desktop workspace for selection, queue management, and generated results. */
const BatchWorkspaceScreen = ({ controller }: BatchWorkspaceScreenProps) => {
  const { t } = useTranslation();
  const {
    act,
    confirmPlan,
    error,
    pending,
    plan,
    prepare,
    reportError,
    retryHydration,
    setPlan,
    state,
    workspace,
  } = controller;
  const [inspectedId, setInspectedId] = useState<null | string>(null);
  const [panel, setPanel] = useState<'details' | 'files'>('files');
  const [isPreviewExpanded, setIsPreviewExpanded] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isDiscardOpen, setIsDiscardOpen] = useState(false);
  const [exportView, setExportView] = useState({
    batchId: '',
    isExpanded: true,
  });
  const isRunning =
    state?.batch.status === 'running' || state?.batch.status === 'stopping';
  const isEditingDisabled =
    !state ||
    isRunning ||
    state.scan.isRunning ||
    ['preparing', 'cancelling'].includes(state.model.status) ||
    [
      'files',
      'folder',
      'include',
      'exports',
      'destination',
      'plan',
      'start',
      'new',
      'model-files',
    ].some((key) => pending.has(key));
  const drop = useNativeDrop(isEditingDisabled, !!state && !!workspace);
  if (!state || !workspace) {
    return (
      <main className="grid h-dvh place-items-center p-8">
        <div className="space-y-4 text-center">
          <p className="text-ink/65 text-sm" role="status">
            {t(error ? 'startup.failed' : 'startup.opening')}
          </p>
          {error && (
            <Button onClick={retryHydration}>{t('startup.retry')}</Button>
          )}
        </div>
      </main>
    );
  }
  const api = window.pywebview.api;
  const items = workspace.items;
  const eligible = items.filter((item) => item.isAvailable);
  const included = new Set(
    items.filter((item) => item.isIncluded).map((item) => item.id),
  );
  const eligibleIds = eligible.map((item) => item.id);
  const extensions = [
    ...new Set(eligible.map((item) => item.extension)),
  ].sort();
  const inspected = items.find((item) => item.id === inspectedId) ?? null;
  const batch = state.batch;
  const activeItem = items.find((item) => item.id === batch.activeItemId);
  const isModelReady = state.model.status === 'ready';
  const hasOnlyExportRetries = items
    .filter((item) => item.isIncluded)
    .every((item) => item.resultId !== null && item.errorStage === 'export');
  const isStartDisabled =
    isEditingDisabled ||
    !included.size ||
    !state.exportSettings.formats.length ||
    (!isModelReady && !hasOnlyExportRetries);
  const isExportOpen =
    exportView.batchId === batch.id
      ? exportView.isExpanded
      : batch.status === 'idle';
  const isPreview =
    import.meta.env.DEV && new URLSearchParams(location.search).has('preview');

  /** Inspect an item without changing its inclusion or switching away from the queue. */
  const inspect = (id: string) => {
    setInspectedId(id);
  };

  /** Copy original transcript text and surface clipboard failures through the command boundary. */
  const copy = (text: string) => {
    navigator.clipboard
      .writeText(text)
      .then(() => toast.success(t('transcript.copiedNotice')))
      .catch(reportError);
  };

  /** Protect unexported session results before clearing the current collection. */
  const newBatch = () => {
    if (items.some((item) => item.resultId && item.errorStage === 'export')) {
      setIsDiscardOpen(true);
    } else {
      act('new', () => api.new_batch());
    }
  };

  return (
    <div className="flex h-dvh min-h-0 flex-col overflow-hidden">
      <a
        className="bg-surface sr-only z-50 rounded-xl p-3 focus:not-sr-only focus:fixed focus:top-4 focus:left-4"
        href="#workspace"
      >
        {t('app.skipContent')}
      </a>
      <header className="border-ink/10 bg-surface/70 flex h-16 shrink-0 items-center justify-between gap-4 border-b px-5 lg:px-7">
        <div className="flex items-center gap-3">
          <img alt="" className="size-8 rounded-lg" src="/logo.svg" />
          <span className="text-base font-semibold tracking-tight">
            Syllentra
          </span>
          <span className="text-ink/25 mx-1 hidden text-lg sm:block">/</span>
          <span className="text-ink/65 hidden text-sm sm:block">
            {t('batch.workspace')}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="border-ink/10 bg-ink/3 text-ink/65 mr-2 hidden items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] sm:inline-flex">
            <span
              className={cn(
                'size-1.5 rounded-full',
                isModelReady ? 'bg-accent' : 'bg-ink/35',
              )}
            />
            Phonon-2.5 <span className="text-ink/65">·</span>{' '}
            {t(`batch.model.${state.model.status}`)}
          </span>
          <Button
            aria-label={t('batch.settings')}
            className="size-9 min-h-9 px-2"
            icon="cog-outline"
            variant="ghost"
            onClick={() => setIsSettingsOpen(true)}
          />
        </div>
      </header>
      <main
        className="mx-auto flex min-h-0 w-full max-w-[1680px] flex-1 flex-col px-4 pt-5 pb-4 lg:px-7 lg:pt-6"
        id="workspace"
        tabIndex={-1}
      >
        <div className="mb-5 flex shrink-0 items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              {t('batch.title')}
            </h1>
            <p className="text-ink/65 mt-1.5 text-sm">{t('batch.intro')}</p>
            <p className="text-ink/65 mt-2 text-xs">
              {t('batch.selectionHelp')}
            </p>
          </div>
          <p className="text-ink/65 hidden items-center gap-1.5 pb-0.5 text-xs md:flex">
            <Icon className="size-3.5" name="shield-check-outline" />
            {t('batch.local')}
          </p>
        </div>
        {isPreview && (
          <p className="border-ink/10 bg-ink/3 text-ink/65 mb-3 shrink-0 rounded-lg border px-3 py-2 text-xs">
            {t('app.previewNotice')}
          </p>
        )}
        {!isModelReady && (
          <section
            aria-label={t('batch.setupTitle')}
            className="border-accent/20 bg-accent/5 mb-4 flex shrink-0 flex-wrap items-center gap-3 rounded-xl border px-4 py-3"
          >
            <Icon className="text-accent size-5 shrink-0" name="waveform" />
            <div className="min-w-48 flex-1">
              <h2 className="text-sm font-semibold">{t('batch.setupTitle')}</h2>
              {state.model.status === 'preparing' ||
              state.model.status === 'cancelling' ? (
                <ModelSetupProgress model={state.model} />
              ) : (
                <p className="text-ink/65 mt-1 text-xs leading-5">
                  {t('batch.setupHint')}
                </p>
              )}
              {state.model.error && (
                <details className="text-danger mt-2 text-xs">
                  <summary className="cursor-pointer">
                    {t('errors.technicalDetails')}
                  </summary>
                  <p className="mt-1 break-words">{state.model.error}</p>
                </details>
              )}
            </div>
            <Button
              disabled={isEditingDisabled || pending.has('model-files')}
              onClick={() => act('model-files', () => api.use_local_model())}
            >
              {t('batch.useLocalModel')}
            </Button>
            {state.model.status === 'preparing' ||
            state.model.status === 'cancelling' ? (
              <Button
                className="text-xs"
                disabled={
                  state.model.status === 'cancelling' ||
                  pending.has('cancel-setup')
                }
                variant="ghost"
                onClick={() => act('cancel-setup', () => api.cancel_setup())}
              >
                {t('common.cancel')}
              </Button>
            ) : (
              <Button
                className="text-xs"
                disabled={isEditingDisabled}
                icon="download"
                onClick={() => act('setup', () => api.setup_model())}
              >
                {t(
                  state.model.status === 'failed'
                    ? 'batch.retrySetup'
                    : 'batch.downloadModel',
                )}
              </Button>
            )}
          </section>
        )}
        {state.notice && (
          <div
            className="border-danger/20 bg-danger/5 text-danger mb-3 shrink-0 rounded-lg border px-3 py-2 text-xs"
            role="alert"
          >
            <details>
              <summary>{t('batch.notice')}</summary>
              <p className="mt-2 break-words">
                {state.notice === 'preferences_unreadable'
                  ? t('batch.preferencesUnreadable')
                  : state.notice}
              </p>
            </details>
          </div>
        )}
        <div
          aria-label={t('batch.panels')}
          className="border-ink/10 mb-3 flex shrink-0 gap-1 rounded-xl border p-1 lg:hidden"
          role="group"
        >
          <button
            aria-pressed={panel === 'files'}
            className={cn(
              'min-h-9 flex-1 rounded-lg px-3 text-sm',
              panel === 'files' && 'bg-surface shadow-xs',
            )}
            type="button"
            onClick={() => setPanel('files')}
          >
            {t('batch.files')}
          </button>
          <button
            aria-pressed={panel === 'details'}
            className={cn(
              'min-h-9 flex-1 rounded-lg px-3 text-sm',
              panel === 'details' && 'bg-surface shadow-xs',
            )}
            type="button"
            onClick={() => setPanel('details')}
          >
            {t('batch.detailsAndExport')}
          </button>
        </div>
        <div className="border-ink/12 bg-surface grid min-h-0 flex-1 overflow-hidden rounded-2xl border shadow-xs lg:grid-cols-[minmax(0,1fr)_360px]">
          <section
            className={cn(
              'relative flex min-h-0 min-w-0 flex-col',
              panel !== 'files' && 'hidden lg:flex',
              drop.isDragging && 'ring-accent/50 ring-2 ring-inset',
            )}
            id="file-dropzone"
            onDragEnter={drop.onDragEnter}
            onDragLeave={drop.onDragLeave}
            onDragOver={drop.onDragOver}
            onDropCapture={drop.onDropCapture}
          >
            <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 px-5 pt-5 pb-4">
              <h2 className="flex items-center gap-2.5 text-sm font-semibold">
                {t('batch.files')}
                <span className="bg-ink/5 text-ink/65 rounded-md px-2 py-0.5 text-xs font-normal tabular-nums">
                  {items.length}
                </span>
              </h2>
              <div className="flex flex-wrap gap-2">
                <Button
                  className="min-h-9 px-3 text-xs"
                  disabled={isEditingDisabled}
                  icon="plus"
                  onClick={() => act('files', () => api.add_files())}
                >
                  {t('batch.addFiles')}
                </Button>
                <Button
                  className="min-h-9 px-3 text-xs"
                  disabled={isEditingDisabled}
                  icon="folder-outline"
                  onClick={() => act('folder', () => api.add_folder())}
                >
                  {t('batch.addFolder')}
                </Button>
                <Button
                  className="min-h-9 px-3 text-xs"
                  disabled={!items.length || isEditingDisabled}
                  icon="refresh"
                  title={t('batch.newBatchHint')}
                  variant="ghost"
                  onClick={newBatch}
                >
                  {t('batch.newBatch')}
                </Button>
              </div>
            </div>
            {items.length > 0 && (
              <>
                <fieldset
                  className="border-ink/8 shrink-0 border-b px-5 pb-3"
                  disabled={isEditingDisabled}
                >
                  <legend className="text-ink/65 mb-2 text-[11px]">
                    {t('batch.fileTypes')}
                  </legend>
                  <div className="flex flex-wrap gap-x-4 gap-y-1">
                    {extensions.map((extension) => {
                      const ids = eligible
                        .filter((item) => item.extension === extension)
                        .map((item) => item.id);
                      const count = ids.filter((id) => included.has(id)).length;
                      return (
                        <Checkbox
                          key={extension}
                          checked={selectionState(ids, included)}
                          disabled={isEditingDisabled}
                          onChange={(isIncluded) =>
                            act('include', () =>
                              api.set_inclusion(ids, isIncluded),
                            )
                          }
                        >
                          <span className="text-xs">
                            {extension.slice(1).toUpperCase()}{' '}
                            <span className="text-ink/65 ml-1 tabular-nums">
                              {count}/{ids.length}
                            </span>
                          </span>
                        </Checkbox>
                      );
                    })}
                  </div>
                </fieldset>
                <div className="border-ink/8 text-ink/65 flex shrink-0 items-center justify-between border-b px-5 py-1.5 text-xs">
                  <Checkbox
                    checked={selectionState(eligibleIds, included)}
                    disabled={isEditingDisabled || !eligibleIds.length}
                    onChange={(isIncluded) =>
                      act('include', () =>
                        api.set_inclusion(eligibleIds, isIncluded),
                      )
                    }
                  >
                    <span className="text-xs">{t('batch.allFiles')}</span>
                  </Checkbox>
                  <span className="pr-1">{t('batch.statusColumn')}</span>
                </div>
              </>
            )}
            {state.scan.isRunning && (
              <div className="bg-accent/5 shrink-0 px-5 py-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-ink/65 text-xs" role="status">
                    {t('batch.scanning', { count: state.scan.discovered })}
                  </p>
                  <Button
                    className="min-h-7 px-2 py-0.5 text-xs"
                    variant="ghost"
                    onClick={() =>
                      act('cancel-import', () => api.cancel_import())
                    }
                  >
                    {t('common.cancel')}
                  </Button>
                </div>
                <progress
                  aria-label={t('batch.scanningLabel')}
                  className="mt-2 h-1 w-full"
                />
              </div>
            )}
            {!items.length && !state.scan.isRunning ? (
              <div className="grid min-h-48 flex-1 place-content-center px-8 py-12 text-center">
                <div className="border-ink/10 bg-ink/3 text-ink/65 mx-auto mb-5 grid size-16 place-items-center rounded-2xl border">
                  <Icon className="size-7" name="upload" />
                </div>
                <h3 className="text-base font-medium">
                  {t(drop.isAvailable ? 'batch.dropTitle' : 'batch.emptyTitle')}
                </h3>
                <p className="text-ink/65 mx-auto mt-2 max-w-72 text-sm leading-6">
                  {t('batch.emptyHint')}
                </p>
                <p className="text-ink/65 mt-5 text-[11px]">
                  MP3, WAV, M4A, MP4, MOV, MKV, FLAC
                </p>
              </div>
            ) : (
              <MediaTree
                inspectedId={inspected?.id ?? null}
                isDisabled={isEditingDisabled}
                workspace={workspace}
                onInclude={(ids, isIncluded) =>
                  act('include', () => api.set_inclusion(ids, isIncluded))
                }
                onInspect={inspect}
              />
            )}
            {drop.isDragging && (
              <div className="border-accent/30 bg-surface/95 pointer-events-none absolute inset-3 z-10 grid place-items-center rounded-xl border-2 border-dashed">
                <p className="text-accent text-base font-medium">
                  {t('batch.dropTitle')}
                </p>
              </div>
            )}
            <footer className="border-ink/8 text-ink/65 shrink-0 border-t px-5 py-3 text-[11px] leading-5">
              {state.scan.isCancelled
                ? t('batch.importCancelled', { count: state.scan.discovered })
                : state.scan.ignored || state.scan.duplicates
                  ? t('batch.importSummary', {
                      duplicates: state.scan.duplicates,
                      ignored: state.scan.ignored,
                    })
                  : t('batch.keyboardHint')}
            </footer>
          </section>
          <aside
            className={cn(
              'border-ink/10 flex min-h-0 min-w-0 flex-col overflow-y-auto border-l',
              panel !== 'details' && 'hidden lg:flex',
            )}
          >
            <div className="border-ink/10 shrink-0 border-b">
              <h2>
                <button
                  aria-controls="export-options"
                  aria-expanded={isExportOpen}
                  className="flex w-full items-center gap-2 px-5 py-4 text-left text-sm font-semibold"
                  type="button"
                  onClick={() =>
                    setExportView({
                      batchId: batch.id,
                      isExpanded: !isExportOpen,
                    })
                  }
                >
                  <Icon
                    className={cn(
                      'text-ink/65 size-3.5',
                      isExportOpen && 'rotate-90',
                    )}
                    name="chevron-right"
                  />
                  {t('batch.exportSettings')}
                  <span className="text-ink/65 ml-auto text-xs font-normal">
                    {state.exportSettings.formats
                      .map((format) => format.toUpperCase())
                      .join(' + ')}
                  </span>
                </button>
              </h2>
              <div hidden={!isExportOpen} id="export-options">
                <ExportSettingsPanel
                  isDisabled={isEditingDisabled}
                  item={inspected}
                  settings={state.exportSettings}
                  onChooseDestination={() =>
                    act('destination', () => api.choose_destination())
                  }
                  onSettings={(settings) =>
                    act('exports', () => api.set_exports(settings))
                  }
                />
              </div>
            </div>
            <ResultInspector
              item={inspected}
              onCopy={copy}
              onExpand={() => setIsPreviewExpanded(true)}
              onOpen={(id, reveal) =>
                act('open', () => api.open_artifact(id, reveal))
              }
            />
          </aside>
        </div>
        <footer className="flex min-h-20 shrink-0 flex-wrap items-center justify-between gap-3 pt-4">
          <div className="min-w-0 flex-1 basis-56">
            {isRunning ? (
              <BatchProgress batch={batch} item={activeItem ?? null} />
            ) : batch.status !== 'idle' ? (
              <>
                <p className="text-sm font-medium">
                  {t(
                    batch.status === 'cancelled'
                      ? 'batch.stopped'
                      : batch.status === 'failed'
                        ? 'batch.failed'
                        : 'batch.finished',
                  )}
                </p>
                <p className="text-ink/65 mt-1 text-xs">
                  {t('batch.outcome', {
                    cancelled: batch.cancelled,
                    completed: batch.completed,
                    failed: batch.failed,
                    skipped: batch.skipped,
                  })}
                  {batch.noSpeech > 0 &&
                    ` · ${t('batch.noSpeechCount', { count: batch.noSpeech })}`}
                </p>
                <BatchSummary batch={batch} />
              </>
            ) : (
              <>
                <p className="text-sm font-medium">
                  {t('batch.selected', { count: included.size })}
                </p>
                <p className="text-ink/65 mt-1 text-xs">
                  {!isModelReady
                    ? t('batch.prepareFirst')
                    : t('batch.conflictsChecked')}
                </p>
              </>
            )}
          </div>
          <div className="flex items-center gap-2">
            {isRunning ? (
              <>
                <Button
                  className="text-xs"
                  disabled={
                    batch.phase === 'cancelling' ||
                    pending.has('cancel') ||
                    !batch.activeItemId
                  }
                  onClick={() => {
                    if (batch.activeItemId) {
                      act('cancel', () =>
                        api.cancel_current(batch.id, batch.activeItemId ?? ''),
                      );
                    }
                  }}
                >
                  {t('batch.cancelCurrent')}
                </Button>
                <Button
                  className="text-xs"
                  disabled={batch.status === 'stopping' || pending.has('stop')}
                  icon="stop"
                  variant="danger"
                  onClick={() => act('stop', () => api.stop_batch(batch.id))}
                >
                  {t('batch.stopBatch')}
                </Button>
              </>
            ) : (
              <>
                {(batch.failed > 0 || batch.cancelled > 0) && (
                  <Button
                    className="text-xs"
                    disabled={
                      isEditingDisabled ||
                      (!isModelReady &&
                        !items
                          .filter(
                            (item) =>
                              item.status === 'failed' ||
                              item.status === 'cancelled',
                          )
                          .every(
                            (item) =>
                              item.resultId && item.errorStage === 'export',
                          ))
                    }
                    icon="refresh"
                    onClick={() => prepare(true)}
                  >
                    {t('batch.retryFailed')}
                  </Button>
                )}
                <Button
                  className="min-w-40"
                  disabled={isStartDisabled}
                  icon="arrow-right"
                  variant="primary"
                  onClick={() => prepare()}
                >
                  {t(
                    pending.has('plan') || pending.has('start')
                      ? 'batch.preparingBatch'
                      : 'batch.startFiles',
                    { count: included.size },
                  )}
                </Button>
              </>
            )}
          </div>
        </footer>
      </main>
      {isPreviewExpanded && inspected && (
        <Modal
          isWide
          title={t('batch.previewTitle')}
          onClose={() => setIsPreviewExpanded(false)}
        >
          <Button className="mt-3" onClick={() => setIsPreviewExpanded(false)}>
            {t('batch.closePreview')}
          </Button>
          <div className="flex h-[70dvh] min-h-0 flex-col">
            <ResultInspector
              item={inspected}
              onCopy={copy}
              onOpen={(id, reveal) =>
                act('open', () => api.open_artifact(id, reveal))
              }
            />
          </div>
        </Modal>
      )}
      {plan && (
        <ConflictReviewDialog
          isPending={pending.has('start')}
          plan={plan}
          onCancel={() => setPlan(null)}
          onConfirm={confirmPlan}
        />
      )}
      {isSettingsOpen && (
        <Modal
          title={t('batch.settings')}
          onClose={() => setIsSettingsOpen(false)}
        >
          <div className="mt-6 space-y-6">
            <div>
              <label
                className="mb-2 block text-sm"
                htmlFor="interface-language"
              >
                {t('app.interfaceLanguage')}
              </label>
              <Select
                disabled={pending.has('appearance')}
                id="interface-language"
                value={state.preferences.interfaceLanguage}
                onChange={(event) => {
                  const language = event.target.value;
                  if (
                    language === 'en' ||
                    language === 'es-ES' ||
                    language === 'system'
                  ) {
                    act('appearance', () =>
                      api.set_appearance(state.preferences.theme, language),
                    );
                  }
                }}
              >
                <option value="system">{t('app.system')}</option>
                <option value="en">English</option>
                <option value="es-ES">Español (España)</option>
              </Select>
            </div>
            <div>
              <p className="mb-3 text-sm">{t('app.appearance')}</p>
              <div
                aria-label={t('app.appearance')}
                className="flex gap-2"
                role="group"
              >
                {themeModes.map((theme) => (
                  <button
                    key={theme}
                    aria-pressed={state.preferences.theme === theme}
                    className={cn(
                      'border-ink/15 min-h-10 flex-1 rounded-lg border px-3 text-sm',
                      state.preferences.theme === theme &&
                        'border-accent/50 bg-accent/10',
                    )}
                    disabled={pending.has('appearance')}
                    type="button"
                    onClick={() =>
                      act('appearance', () =>
                        api.set_appearance(
                          theme,
                          state.preferences.interfaceLanguage,
                        ),
                      )
                    }
                  >
                    {t(`app.${theme}`)}
                  </button>
                ))}
              </div>
            </div>
            <div className="border-ink/10 border-t pt-5">
              <p className="text-sm font-medium">{state.modelInfo.name}</p>
              <p className="text-ink/65 mt-2 text-xs leading-6">
                {t('batch.modelAbout')}
              </p>
              <details className="mt-3 text-xs leading-6">
                <summary className="cursor-pointer font-medium">
                  {t('batch.supportedLanguages', {
                    count: state.modelInfo.languages.length,
                  })}
                </summary>
                <p className="text-ink/65 mt-2">
                  {t('batch.supportedLanguagesHint')}
                </p>
                <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                  {state.modelInfo.languages.map((code) => (
                    <li key={code}>
                      {t(`batch.spokenLanguages.${code}`, {
                        defaultValue: code,
                      })}
                    </li>
                  ))}
                </ul>
              </details>
              <p className="text-ink/65 mt-3 text-xs leading-5">
                {t('batch.modelStorageHelp')}
              </p>
              <p className="text-ink/65 mt-2 text-xs leading-5">
                {t('batch.portableHelp')}
              </p>
              <p className="mt-3 text-xs font-medium">
                {t('batch.dataDirectory')}
              </p>
              <code className="text-ink/65 mt-1 block text-xs break-all">
                {state.modelLocation.dataDirectory}
              </code>
              <p className="mt-3 text-xs font-medium">
                {t('batch.modelLocation')}
              </p>
              <code className="text-ink/65 mt-1 block text-xs break-all">
                {state.modelLocation.path}
              </code>
              <p className="mt-3 text-xs font-medium">
                {t('batch.downloadLocation')}
              </p>
              <code className="text-ink/65 mt-1 block text-xs break-all">
                {state.modelLocation.downloadDirectory}
              </code>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button
                  disabled={isEditingDisabled || pending.has('model-files')}
                  onClick={() =>
                    act('model-files', () => api.use_local_model())
                  }
                >
                  {t('batch.useLocalModel')}
                </Button>
                <Button
                  disabled={isEditingDisabled || pending.has('model-files')}
                  onClick={() =>
                    act('model-files', () => api.choose_model_storage())
                  }
                >
                  {t('batch.chooseModelStorage')}
                </Button>
                <Button
                  disabled={
                    isEditingDisabled ||
                    !isModelReady ||
                    pending.has('model-files')
                  }
                  onClick={() => act('model-files', () => api.backup_model())}
                >
                  {t('batch.backupModel')}
                </Button>
              </div>
              <a
                className="text-accent mt-2 inline-block text-xs underline underline-offset-4"
                href={state.modelInfo.sourceUrl}
                rel="noreferrer"
                target="_blank"
              >
                {t('batch.modelSource')}
              </a>
            </div>
          </div>
          <footer className="mt-6 flex justify-end">
            <Button onClick={() => setIsSettingsOpen(false)}>
              {t('batch.done')}
            </Button>
          </footer>
        </Modal>
      )}
      {isDiscardOpen && (
        <Modal
          title={t('batch.discardTitle')}
          onClose={() => setIsDiscardOpen(false)}
        >
          <p className="text-ink/65 mt-4 text-sm leading-6">
            {t('batch.discardHint')}
          </p>
          <footer className="mt-6 flex justify-end gap-2">
            <Button onClick={() => setIsDiscardOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                setIsDiscardOpen(false);
                act('new', () => api.new_batch(true));
              }}
            >
              {t('batch.discard')}
            </Button>
          </footer>
        </Modal>
      )}
      {state.closeRequested && (
        <Modal
          isDismissible={!pending.has('quit')}
          title={t('batch.quitTitle')}
          onClose={() => act('keep', () => api.keep_open())}
        >
          <p className="text-ink/65 mt-4 text-sm leading-6">
            {t('batch.quitHint')}
          </p>
          <footer className="mt-6 flex justify-end gap-2">
            <Button
              disabled={pending.has('quit')}
              onClick={() => act('keep', () => api.keep_open())}
            >
              {t('batch.keepOpen')}
            </Button>
            <Button
              disabled={pending.has('quit')}
              variant="danger"
              onClick={() => act('quit', () => api.quit_app())}
            >
              {t(
                pending.has('quit')
                  ? 'batch.stoppingAndQuitting'
                  : 'batch.stopAndQuit',
              )}
            </Button>
          </footer>
        </Modal>
      )}
    </div>
  );
};

export default BatchWorkspaceScreen;
