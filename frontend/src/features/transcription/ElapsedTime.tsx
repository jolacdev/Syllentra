import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

type ElapsedTimeProps = { seconds: number; isRunning: boolean };

/** Advance the backend's measured elapsed time locally without sending synthetic inference progress. */
const ElapsedTime = ({ seconds, isRunning }: ElapsedTimeProps) => {
  const { t } = useTranslation();
  const [clock, setClock] = useState({ additional: 0, seconds });
  useEffect(() => {
    if (!isRunning) {
      return;
    }
    const started = performance.now();
    const timer = window.setInterval(
      () =>
        setClock({
          additional: Math.max(0, performance.now() - started) / 1000,
          seconds,
        }),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [isRunning, seconds]);
  const elapsed = Math.floor(
    seconds + (isRunning && clock.seconds === seconds ? clock.additional : 0),
  );
  const time = `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, '0')}`;
  return (
    <span className="text-ink/65 text-xs tabular-nums">
      {t('batch.elapsed', { time })}
    </span>
  );
};

export default ElapsedTime;
