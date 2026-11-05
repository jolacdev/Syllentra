/* eslint-disable perfectionist/sort-objects */
const SIZE_UNITS = {
  Bytes: 1,
  KB: 1024,
  MB: 1024 ** 2,
  GB: 1024 ** 3,
  TB: 1024 ** 4,
  PB: 1024 ** 5,
  EB: 1024 ** 6,
  ZB: 1024 ** 7,
  YB: 1024 ** 8,
} as const;

export type FileSizeUnit = keyof typeof SIZE_UNITS;

const DEFAULT_DECIMALS = 2;

/** Format byte sizes consistently in file previews. */
export const formatSizeUnit = (
  value: number,
  from: FileSizeUnit = 'Bytes',
  to: FileSizeUnit = 'MB',
  decimals = DEFAULT_DECIMALS,
) => {
  if (isNaN(value) || value <= 0) {
    return '0 Bytes';
  }

  const fractionDigits = decimals < 0 ? DEFAULT_DECIMALS : decimals;

  if (from === to) {
    return `${value.toFixed(fractionDigits)} ${to}`;
  }

  const bytes = value * SIZE_UNITS[from];
  const convertedValue = bytes / SIZE_UNITS[to];

  return `${convertedValue.toFixed(fractionDigits)} ${to}`;
};
