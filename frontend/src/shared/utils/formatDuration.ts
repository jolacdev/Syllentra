/** Format measured durations as an hours, minutes, and seconds clock without decimals. */
export const formatDuration = (seconds: number) => {
  const whole = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const remaining = String(whole % 60).padStart(2, '0');
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${remaining}`;
};
