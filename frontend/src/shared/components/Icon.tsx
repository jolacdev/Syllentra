import {
  mdiArrowRight,
  mdiCheck,
  mdiChevronDown,
  mdiChevronRight,
  mdiClockOutline,
  mdiClose,
  mdiCogOutline,
  mdiContentCopy,
  mdiDeleteOutline,
  mdiDownload,
  mdiFileDocumentOutline,
  mdiFolderOutline,
  mdiInformationOutline,
  mdiLayersOutline,
  mdiMinus,
  mdiMonitor,
  mdiOpenInNew,
  mdiPlus,
  mdiRefresh,
  mdiShieldCheckOutline,
  mdiStop,
  mdiUpload,
  mdiWaveform,
  mdiWeatherNight,
  mdiWeatherSunny,
} from '@mdi/js';

/** MDI icons use their source slugs: https://pictogrammers.com/library/mdi/. */
const icons = {
  'arrow-right': mdiArrowRight,
  check: mdiCheck,
  'chevron-down': mdiChevronDown,
  'chevron-right': mdiChevronRight,
  'clock-outline': mdiClockOutline,
  close: mdiClose,
  'cog-outline': mdiCogOutline,
  'content-copy': mdiContentCopy,
  'delete-outline': mdiDeleteOutline,
  download: mdiDownload,
  'file-document-outline': mdiFileDocumentOutline,
  'folder-outline': mdiFolderOutline,
  'information-outline': mdiInformationOutline,
  'layers-outline': mdiLayersOutline,
  minus: mdiMinus,
  monitor: mdiMonitor,
  'open-in-new': mdiOpenInNew,
  plus: mdiPlus,
  refresh: mdiRefresh,
  'shield-check-outline': mdiShieldCheckOutline,
  stop: mdiStop,
  upload: mdiUpload,
  waveform: mdiWaveform,
  'weather-night': mdiWeatherNight,
  'weather-sunny': mdiWeatherSunny,
} as const;

export type IconName = keyof typeof icons;
type IconProps = { name: IconName; className?: string; size?: number };

/** Render only registered MDI icons; callers cannot inject arbitrary SVG paths. */
const Icon = ({ className = undefined, name, size = 20 }: IconProps) => (
  <svg
    aria-hidden="true"
    className={className}
    fill="currentColor"
    focusable="false"
    height={size}
    viewBox="0 0 24 24"
    width={size}
  >
    <path d={icons[name]} />
  </svg>
);

export default Icon;
