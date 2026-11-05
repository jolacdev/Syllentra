import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import type { BatchState } from 'types/pywebview/pywebview-api';

import i18n from '../../../i18n/i18n';
import BatchSummary from '../BatchSummary';

const batch: BatchState = {
  activeItemId: null,
  id: 'finished',
  cancelled: 0,
  completed: 1,
  elapsedSeconds: 90,
  failed: 0,
  noSpeech: 0,
  phase: '',
  progress: null,
  skipped: 0,
  status: 'completed',
  total: 1,
};

beforeEach(async () => {
  await i18n.changeLanguage('en');
});

afterEach(cleanup);

describe('batch results', () => {
  it('shows total elapsed time', () => {
    render(<BatchSummary batch={batch} />);
    expect(screen.getByText('Time spent 00:01:30')).toBeVisible();
  });

  it('keeps partial results visible after cancellation and formats hours', () => {
    render(
      <BatchSummary
        batch={{
          ...batch,
          elapsedSeconds: 3723.4,
          status: 'cancelled',
        }}
      />,
    );
    expect(screen.getByText('Time spent 01:02:03')).toBeVisible();
  });

  it('handles zero elapsed time', () => {
    render(<BatchSummary batch={{ ...batch, elapsedSeconds: 0 }} />);
    expect(screen.getByText('Time spent 00:00:00')).toBeVisible();
  });

  it('translates the elapsed-time label', async () => {
    await i18n.changeLanguage('es-ES');
    render(<BatchSummary batch={batch} />);
    expect(screen.getByText('Tiempo empleado 00:01:30')).toBeVisible();
  });
});
