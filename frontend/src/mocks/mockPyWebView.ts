import {
  getSubtitleLanguage,
  outputName,
} from '@features/transcription/exportNames';
import type {
  AudioSelection,
  BatchAppState,
  BatchPlan,
  CommandReply,
  ExportSettings,
  MediaItem,
  PyWebViewApi,
  TranscriptPage,
  WorkspaceDelta,
} from 'types/pywebview/pywebview-api';
import type { PyWebViewStateEvent } from 'types/pywebview/pywebview-state';

/** Start the simulated batch with the same export defaults as the native app. */
const defaultExports = (): ExportSettings => ({
  destination: null,
  formats: ['srt'],
  includeAudioLanguage: false,
});

/** Create deterministic nested media without implying access to native files in browser development. */
const previewFiles = (isLarge: boolean): MediaItem[] => {
  const paths = isLarge
    ? Array.from(
        { length: 10_000 },
        (_, index) =>
          `Session ${Math.floor(index / 100) + 1}/Recording ${index + 1}.wav`,
      )
    : [
        'Episode 01/Interview with Jane.mp3',
        'Episode 01/Camera audio.mp4',
        'Episode 02/Field recording.wav',
        'Episode 02/Interview with John.mp3',
        'Episode 02/Room tone.wav',
        'Opening notes.m4a',
      ];
  const files: MediaItem[] = paths.map((path, index) => ({
    id: `file-${index}`,
    resultId: null,
    rootId: 'series',
    error: null,
    errorStage: null,
    extension: `.${path.split('.').pop() ?? 'wav'}`,
    modifiedNs: '0',
    name: path.split('/').pop() ?? path,
    noSpeech: false,
    outputs: [],
    path: `/Preview/Research interviews/${path}`,
    relativePath: path,
    size: 4_856_108 + index * 562_405,
    status: 'ready',
    audio: {
      overrideIndex: null,
      probeError: null,
      reason: 'single',
      selectedIndex: 0,
      tracks: [
        {
          channels: 2,
          codec: 'aac',
          index: 0,
          language: 'es',
          number: 1,
          rawLanguage: 'spa',
          title: '',
          isAudioDescription: false,
          isCommentary: false,
          isDefault: true,
        },
      ],
    },
    isAvailable: true,
    isIncluded: index !== 4,
  }));
  if (!isLarge) {
    const camera = files[1];
    const notes = files[5];
    // Two non-audio streams precede the camera audio, so stream indexes differ from track numbers.
    camera.audio = {
      ...camera.audio,
      reason: 'default',
      selectedIndex: 2,
      tracks: [
        {
          ...camera.audio.tracks[0],
          index: 2,
          number: 1,
          title: 'Spanish dialogue',
        },
        {
          ...camera.audio.tracks[0],
          index: 3,
          language: 'en',
          number: 2,
          rawLanguage: 'eng',
          title: 'English dialogue',
          isDefault: false,
        },
      ],
    };
    notes.audio = {
      ...notes.audio,
      reason: 'default',
      tracks: [
        { ...notes.audio.tracks[0], language: 'fr', rawLanguage: 'fra' },
        {
          ...notes.audio.tracks[0],
          index: 1,
          language: 'de',
          number: 2,
          rawLanguage: 'deu',
          isDefault: false,
        },
      ],
    };
  }
  return files;
};

/** Mirror backend selection and cache invalidation for the development preview. */
const updatePreviewAudio = (item: MediaItem, language: null | string) => {
  const audio = item.audio;
  const tracks = audio.tracks;
  const override = tracks.find((track) => track.index === audio.overrideIndex);
  const matches = tracks
    .filter((track) => language && track.language === language)
    .sort(
      (left, right) =>
        Number(left.isCommentary || left.isAudioDescription) -
          Number(right.isCommentary || right.isAudioDescription) ||
        Number(right.isDefault) - Number(left.isDefault) ||
        left.number - right.number,
    );
  let track = tracks.find((entry) => entry.isDefault) ?? tracks[0];
  let reason: AudioSelection['reason'] = language ? 'fallback' : 'default';
  if (override) {
    track = override;
    reason = 'override';
  } else if (tracks.length === 1) {
    reason = 'single';
  } else if (matches.length) {
    track = matches[0];
    reason = 'preferred';
  }
  const index = track?.index ?? null;
  if (index !== audio.selectedIndex) {
    item.resultId = null;
    item.outputs = [];
    item.noSpeech = false;
    item.status = 'ready';
    item.error = null;
    item.errorStage = null;
  }
  audio.selectedIndex = index;
  audio.reason = track ? reason : 'unavailable';
};

/** Install the generated bridge contract only for an explicitly requested development preview. */
export const createPyWebViewMock = () => {
  if (window.pywebview?.api) {
    return;
  }
  const scenario = new URLSearchParams(location.search).get('preview');
  const listeners = new Set<(event: PyWebViewStateEvent) => void>();
  const results = new Map<string, TranscriptPage>();
  const collection: WorkspaceDelta = {
    items: [],
    reset: true,
    revision: 0,
    roots: [],
  };
  let plan: BatchPlan | null = null;
  let timer: null | number = null;
  let setupTimer: null | number = null;
  let queue: string[] = [];
  let position = 0;
  let state: BatchAppState = {
    closeRequested: false,
    collectionRevision: 0,
    exportSettings: defaultExports(),
    notice: null,
    revision: 0,
    batch: {
      activeItemId: null,
      id: '',
      cancelled: 0,
      completed: 0,
      elapsedSeconds: 0,
      failed: 0,
      noSpeech: 0,
      phase: '',
      progress: null,
      skipped: 0,
      status: 'idle',
      total: 0,
    },
    model: {
      elapsedSeconds: 0,
      error: null,
      status: scenario ? 'ready' : 'missing',
    },
    modelInfo: {
      name: 'Phonon-2.5 Multilingual',
      sourceUrl: 'https://www.fermionresearch.com/models/phonon-2-5/',
      languages: [
        'en',
        'es',
        'fr',
        'de',
        'it',
        'pt',
        'nl',
        'pl',
        'ru',
        'uk',
        'ro',
        'cs',
        'sk',
        'bg',
        'hr',
        'sv',
        'da',
        'fi',
        'et',
        'lv',
        'lt',
        'hu',
        'sl',
        'mt',
        'el',
      ],
    },
    modelLocation: {
      dataDirectory: '/Preview/Syllentra Data',
      downloadDirectory: '/Preview/Models',
      path: '/Preview/Models/model_phonon25_f25x1_48k_int6',
    },
    preferences: {
      interfaceLanguage: 'system',
      preferredAudioLanguage: null,
      theme: 'system',
      version: 2,
    },
    scan: {
      currentPath: '',
      discovered: 0,
      duplicates: 0,
      ignored: 0,
      isCancelled: false,
      isRunning: false,
    },
  };

  /** Emit immutable state snapshots using the same top-level event contract as the native app. */
  const emit = (isCollectionChanged = false) => {
    if (isCollectionChanged) {
      collection.revision += 1;
    }
    state = structuredClone({
      ...state,
      collectionRevision: collection.revision,
      revision: state.revision + 1,
    });
    const detail: PyWebViewStateEvent['detail'] = { key: 'app', value: state };
    const event = new CustomEvent('change', { detail });
    listeners.forEach((listener) => listener(event));
  };

  /** Return the native command success shape without promising a desktop side effect. */
  const success = (): Promise<CommandReply> => Promise.resolve({ error: null });

  /** Populate one simulated recursively imported collection for interaction and scale reviews. */
  const populate = () => {
    collection.roots = [
      {
        id: 'series',
        alias: 'Research interviews',
        name: 'Research interviews',
        path: '/Preview/Research interviews',
        isFolder: true,
      },
    ];
    collection.items = previewFiles(scenario === 'large');
    state.scan.discovered = collection.items.length;
    emit(true);
  };

  /** Advance the simulated queue serially while leaving inspection and completed outputs available. */
  const next = () => {
    if (position >= queue.length) {
      state.batch.status = 'completed';
      state.batch.activeItemId = null;
      state.batch.phase = '';
      emit();
      return;
    }
    const item = collection.items.find(
      (candidate) => candidate.id === queue[position],
    );
    position += 1;
    if (!item) {
      next();
      return;
    }
    state.batch.activeItemId = item.id;
    item.status = 'preparing';
    state.batch.phase = 'preparing';
    state.batch.progress = null;
    emit(true);
    timer = window.setTimeout(() => {
      item.status = 'transcribing';
      state.batch.phase = 'transcribing';
      state.batch.progress = 50;
      emit(true);
      timer = window.setTimeout(() => {
        if (scenario === 'error' && position === 2) {
          item.status = 'failed';
          item.errorStage = 'inference';
          item.error = 'Simulated decoder failure';
          state.batch.failed += 1;
        } else {
          item.status = 'completed';
          item.resultId = `result-${item.id}`;
          item.outputs = item.outputs.map((output) => ({
            ...output,
            status: output.action === 'skip' ? 'skipped' : 'written',
          }));
          state.batch.completed += 1;
          results.set(item.id, {
            id: item.resultId,
            duration: 24.5,
            offset: 0,
            processingSeconds: 1.4,
            text: 'This is a simulated transcript. Each recording is processed on your computer. Completed transcripts are exported automatically beside the source file.',
            totalSegments: 3,
            segments: [
              {
                id: 0,
                end: 6,
                start: 0,
                text: 'This is a simulated transcript.',
              },
              {
                id: 1,
                end: 14,
                start: 6.5,
                text: 'Each recording is processed on your computer.',
              },
              {
                id: 2,
                end: 24.5,
                start: 15,
                text: 'Completed transcripts are exported\nautomatically beside the source file.',
              },
            ],
          });
        }
        state.batch.elapsedSeconds += 1.4;
        emit(true);
        next();
      }, 900);
    }, 350);
  };

  const api: PyWebViewApi = {
    add_files: () => {
      populate();
      return success();
    },
    add_folder: () => {
      populate();
      return success();
    },
    backup_model: () => Promise.resolve({ error: null }),
    bind_dropzone: () => Promise.resolve(false),
    cancel_current: (batchId, itemId) => {
      if (state.batch.id === batchId && state.batch.activeItemId === itemId) {
        if (timer !== null) {
          window.clearTimeout(timer);
        }
        const item = collection.items.find(
          (candidate) => candidate.id === itemId,
        );
        if (item) {
          item.status = 'cancelled';
        }
        state.batch.cancelled += 1;
        emit(true);
        next();
      }
      return success();
    },
    cancel_import: () => success(),
    cancel_setup: () => {
      if (setupTimer !== null) {
        window.clearTimeout(setupTimer);
      }
      state.model.status = 'missing';
      emit();
      return success();
    },
    choose_destination: () => {
      state.exportSettings.destination = '/Preview/Exports';
      emit();
      return success();
    },
    choose_model_storage: () => Promise.resolve({ error: null }),
    get_state: () => Promise.resolve(structuredClone(state)),
    get_transcript: (itemId) => {
      const result = results.get(itemId);
      return result
        ? Promise.resolve(structuredClone(result))
        : Promise.reject(new Error('No preview result available.'));
    },
    get_workspace: () => Promise.resolve(structuredClone(collection)),
    keep_open: () => {
      state.closeRequested = false;
      emit();
      return success();
    },
    new_batch: () => {
      if (timer !== null) {
        window.clearTimeout(timer);
      }
      collection.items = [];
      collection.roots = [];
      state.batch = {
        ...state.batch,
        activeItemId: null,
        id: '',
        cancelled: 0,
        completed: 0,
        elapsedSeconds: 0,
        failed: 0,
        noSpeech: 0,
        phase: '',
        progress: null,
        skipped: 0,
        status: 'idle',
        total: 0,
      };
      state.exportSettings = defaultExports();
      results.clear();
      emit(true);
      return success();
    },
    open_artifact: () =>
      Promise.resolve({
        error: {
          code: 'unavailable',
          details: 'Opening generated files requires the desktop app.',
        },
      }),
    prepare_batch: (failedOnly = false) => {
      const selected = collection.items.filter((item) =>
        failedOnly
          ? item.status === 'failed' || item.status === 'cancelled'
          : item.isIncluded,
      );
      plan = {
        id: crypto.randomUUID(),
        revision: collection.revision,
        items: selected.map((item, index) => {
          const subtitleLanguage = getSubtitleLanguage(
            item,
            state.exportSettings,
          );
          const stem = item.path.replace(/\.[^.]+$/, '');
          return {
            itemId: item.id,
            resultId: null,
            audioStreamIndex: item.audio.selectedIndex,
            modifiedNs: item.modifiedNs,
            size: item.size,
            sourcePath: item.path,
            subtitleLanguage,
            outputs: state.exportSettings.formats.map((format) => ({
              id: crypto.randomUUID(),
              conflict: scenario === 'conflicts' && index === 0,
              error: null,
              existingSignature: null,
              format,
              path: outputName(stem, format, subtitleLanguage),
              status: 'planned',
              action:
                scenario === 'conflicts' && index === 0 ? 'ask' : 'create',
            })),
          };
        }),
      };
      return Promise.resolve({ error: null, plan: structuredClone(plan) });
    },
    quit_app: () =>
      Promise.resolve({
        error: {
          code: 'unavailable',
          details: 'Quitting requires the desktop app.',
        },
      }),
    resolve_conflicts: (planId, ids, action) => {
      if (plan?.id !== planId) {
        return Promise.resolve({
          error: { code: 'invalid_request', details: 'The plan changed.' },
          plan: null,
        });
      }
      plan.items.forEach((item) =>
        item.outputs.forEach((output) => {
          if (ids.includes(output.id)) {
            output.action = action;
          }
        }),
      );
      return Promise.resolve({ error: null, plan: structuredClone(plan) });
    },
    select_audio_track: (itemId, index) => {
      const item = collection.items.find((entry) => entry.id === itemId);
      if (item) {
        item.audio.overrideIndex = index;
        updatePreviewAudio(item, state.preferences.preferredAudioLanguage);
      }
      plan = null;
      emit(true);
      return success();
    },
    set_appearance: (theme, interfaceLanguage) => {
      state.preferences = {
        ...state.preferences,
        interfaceLanguage,
        theme,
        version: 2,
      };
      emit();
      return success();
    },
    set_audio_language: (language) => {
      state.preferences.preferredAudioLanguage = language;
      collection.items.forEach((item) => updatePreviewAudio(item, language));
      plan = null;
      emit(true);
      return success();
    },
    set_exports: (settings) => {
      state.exportSettings = structuredClone(settings);
      plan = null;
      emit();
      return success();
    },
    set_inclusion: (ids, isIncluded) => {
      collection.items.forEach((item) => {
        if (ids.includes(item.id)) {
          item.isIncluded = isIncluded && item.isAvailable;
        }
      });
      emit(true);
      return success();
    },
    setup_model: () => {
      state.model.elapsedSeconds = 0;
      state.model.status = 'preparing';
      emit();
      setupTimer = window.setTimeout(() => {
        state.model.status = 'ready';
        state.model.elapsedSeconds = 6;
        emit();
      }, 6000);
      return success();
    },
    start_batch: (planId) => {
      if (plan?.id !== planId) {
        return Promise.resolve({
          error: { code: 'invalid_request', details: 'The plan changed.' },
        });
      }
      queue = plan.items.map((item) => item.itemId);
      position = 0;
      state.batch = {
        ...state.batch,
        id: crypto.randomUUID(),
        cancelled: 0,
        completed: 0,
        elapsedSeconds: 0,
        failed: 0,
        noSpeech: 0,
        skipped: 0,
        status: 'running',
        total: queue.length,
      };
      plan.items.forEach((planned) => {
        const item = collection.items.find(
          (candidate) => candidate.id === planned.itemId,
        );
        if (item) {
          item.status = 'queued';
          item.outputs = structuredClone(planned.outputs);
        }
      });
      emit(true);
      next();
      return success();
    },
    stop_batch: (batchId) => {
      if (batchId === state.batch.id) {
        if (timer !== null) {
          window.clearTimeout(timer);
        }
        collection.items.forEach((item) => {
          if (
            ['queued', 'preparing', 'transcribing', 'exporting'].includes(
              item.status,
            )
          ) {
            item.status = 'cancelled';
            state.batch.cancelled += 1;
          }
        });
        state.batch.status = 'cancelled';
        state.batch.activeItemId = null;
        state.batch.phase = '';
        emit(true);
      }
      return success();
    },
    use_local_model: () => Promise.resolve({ error: null }),
  };
  if (scenario && scenario !== 'empty') {
    populate();
  }
  window.pywebview = {
    api,
    state: {
      addEventListener: (_type, callback) => {
        listeners.add(callback);
      },
      get app() {
        return state;
      },
      removeEventListener: (_type, callback) => {
        listeners.delete(callback);
      },
    },
  };
};
