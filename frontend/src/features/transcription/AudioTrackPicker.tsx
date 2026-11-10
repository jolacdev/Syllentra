import { useId } from 'react';
import { useTranslation } from 'react-i18next';

import Select from '@components/Select';
import type { AudioTrack, MediaItem } from 'types/pywebview/pywebview-api';

type AudioTrackPickerProps = {
  item: MediaItem;
  isDisabled: boolean;
  onSelect: (index: null | number) => void;
};

/** Expose a file-specific override while keeping automatic batch selection as the normal path. */
const AudioTrackPicker = ({
  item,
  onSelect,
  isDisabled,
}: AudioTrackPickerProps) => {
  const { t } = useTranslation();
  const id = useId();
  const audio = item.audio;
  const selected = audio.tracks.find(
    (track) => track.index === audio.selectedIndex,
  );
  /** Label audio ordinals separately from the actual stream index used by the decoder. */
  const label = (track: AudioTrack) =>
    [
      t('audio.trackNumber', { number: track.number }),
      track.language
        ? t(`batch.spokenLanguages.${track.language}`, {
            defaultValue: track.language,
          })
        : track.rawLanguage || t('audio.unknownLanguage'),
      track.rawLanguage?.includes('-') ? `(${track.rawLanguage})` : '',
      track.title,
      `${track.codec} · ${t('audio.channels', { count: track.channels })}`,
      track.isDefault ? t('audio.defaultFlag') : '',
      track.isCommentary ? t('audio.commentary') : '',
      track.isAudioDescription ? t('audio.description') : '',
    ]
      .filter(Boolean)
      .join(' · ');
  return (
    <div className="mt-4">
      <label className="mb-2 block text-xs font-medium" htmlFor={id}>
        {t('audio.selectedTrack')}
      </label>
      {audio.tracks.length > 1 ? (
        <Select
          disabled={isDisabled}
          id={id}
          value={audio.overrideIndex ?? ''}
          onChange={(event) =>
            onSelect(
              event.target.value === '' ? null : Number(event.target.value),
            )
          }
        >
          <option value="">{t('audio.automatic')}</option>
          {audio.tracks.map((track) => (
            <option key={track.index} value={track.index}>
              {label(track)}
            </option>
          ))}
        </Select>
      ) : null}
      {selected && (
        <p className="text-ink/65 mt-2 text-xs leading-5">{label(selected)}</p>
      )}
      <p className="text-ink/65 mt-1 text-xs leading-5">
        {t(`audio.reason.${audio.reason}`)}
      </p>
      {audio.probeError && (
        <details className="text-ink/65 mt-2 text-xs">
          <summary className="cursor-pointer">
            {t('errors.technicalDetails')}
          </summary>
          <p className="mt-1 break-words">{audio.probeError}</p>
        </details>
      )}
    </div>
  );
};

export default AudioTrackPicker;
