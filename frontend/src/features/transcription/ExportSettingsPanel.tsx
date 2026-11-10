import { useTranslation } from 'react-i18next';

import Button from '@components/Button';
import Checkbox from '@components/Checkbox';
import Icon from '@components/Icon';
import type { ExportSettings, MediaItem } from 'types/pywebview/pywebview-api';

import { getSubtitleLanguage, outputName } from './exportNames';

type ExportSettingsPanelProps = {
  item: MediaItem | null;
  settings: ExportSettings;
  isDisabled: boolean;
  onChooseDestination: () => void;
  onSettings: (settings: ExportSettings) => void;
};

const formats: ExportSettings['formats'] = ['srt', 'txt', 'vtt'];

/** Keep independent export formats and destination choices visible beside the collection. */
const ExportSettingsPanel = ({
  item,
  onChooseDestination,
  onSettings,
  settings,
  isDisabled,
}: ExportSettingsPanelProps) => {
  const { t } = useTranslation();
  const example = outputName(
    item?.name.replace(/\.[^.]+$/, '') ?? t('batch.recordingExample'),
    settings.formats[0] ?? 'srt',
    getSubtitleLanguage(item, settings),
  );
  return (
    <div className="px-5 pt-1 pb-5">
      <fieldset className="mt-0" disabled={isDisabled}>
        <legend className="text-ink/65 text-xs">{t('batch.formats')}</legend>
        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1">
          {formats.map((format) => (
            <Checkbox
              key={format}
              checked={settings.formats.includes(format)}
              disabled={isDisabled}
              onChange={(isIncluded) =>
                onSettings({
                  ...settings,
                  formats: isIncluded
                    ? [...settings.formats, format]
                    : settings.formats.filter((value) => value !== format),
                })
              }
            >
              <span className="font-medium">{format.toUpperCase()}</span>
            </Checkbox>
          ))}
        </div>
      </fieldset>
      {!settings.formats.length && (
        <p className="text-danger mt-1 text-xs" role="status">
          {t('batch.selectFormat')}
        </p>
      )}
      <div className="mt-2">
        <Checkbox
          checked={settings.includeAudioLanguage}
          disabled={
            isDisabled || !settings.formats.some((format) => format !== 'txt')
          }
          onChange={(includeAudioLanguage) =>
            onSettings({ ...settings, includeAudioLanguage })
          }
        >
          {t('batch.includeAudioLanguage')}
        </Checkbox>
        <p className="text-ink/65 ml-6 text-xs leading-5">
          {t('batch.includeAudioLanguageHint')}
        </p>
      </div>
      <fieldset className="mt-4 space-y-3" disabled={isDisabled}>
        <legend className="text-ink/65 mb-2 text-xs">
          {t('batch.destination')}
        </legend>
        <label className="flex items-center gap-2.5 text-sm">
          <input
            checked={settings.destination === null}
            className="accent-accent size-4"
            name="destination"
            type="radio"
            onChange={() => onSettings({ ...settings, destination: null })}
          />
          {t('batch.besideSources')}
        </label>
        <label className="flex items-center gap-2.5 text-sm">
          <input
            checked={settings.destination !== null}
            className="accent-accent size-4"
            name="destination"
            type="radio"
            onChange={onChooseDestination}
          />
          {t('batch.customDestination')}
        </label>
        {settings.destination !== null && (
          <div className="border-ink/12 bg-canvas/60 ml-6 rounded-lg border p-3">
            <p className="truncate text-xs" title={settings.destination}>
              {settings.destination}
            </p>
            <Button
              className="mt-2 min-h-8 px-2 py-1 text-xs"
              disabled={isDisabled}
              icon="folder-outline"
              variant="ghost"
              onClick={onChooseDestination}
            >
              {t('batch.changeFolder')}
            </Button>
          </div>
        )}
      </fieldset>
      <div className="text-ink/65 mt-5 flex gap-2 text-xs leading-5">
        <Icon
          className="mt-0.5 size-3.5 shrink-0"
          name="file-document-outline"
        />
        <div className="min-w-0">
          <p className="truncate font-mono" title={example}>
            {example}
          </p>
          <p className="mt-0.5">
            {t(
              settings.destination === null
                ? 'batch.besideHint'
                : 'batch.hierarchyHint',
            )}
          </p>
        </div>
      </div>
    </div>
  );
};

export default ExportSettingsPanel;
