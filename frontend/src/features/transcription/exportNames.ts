import type { ExportSettings, MediaItem } from 'types/pywebview/pywebview-api';

/** Read the selected track’s language for simulated exports and filename examples. */
export const getSubtitleLanguage = (
  item: MediaItem | null,
  settings: ExportSettings,
) =>
  settings.includeAudioLanguage && item
    ? (item.audio.tracks.find(
        (track) => track.index === item.audio.selectedIndex,
      )?.language ?? null)
    : null;

/** Format the suffix used by the backend for subtitle files. */
export const outputName = (
  stem: string,
  format: ExportSettings['formats'][number],
  language: null | string,
) => `${stem}${language && format !== 'txt' ? `.${language}` : ''}.${format}`;
