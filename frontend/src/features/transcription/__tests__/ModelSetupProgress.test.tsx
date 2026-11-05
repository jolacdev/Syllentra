import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import i18n from '../../../i18n/i18n';
import ModelSetupProgress from '../ModelSetupProgress';

beforeEach(async () => {
  await i18n.changeLanguage('en');
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('model preparation feedback', () => {
  it('shows status and advances recovered elapsed time without a progress bar', async () => {
    vi.useFakeTimers();
    const clock = vi.spyOn(performance, 'now').mockReturnValue(0);
    render(
      <ModelSetupProgress
        model={{ elapsedSeconds: 37, error: null, status: 'preparing' }}
      />,
    );
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(
      'Downloading and preparing the model…',
    );
    expect(screen.getByText('00:00:37 elapsed')).toBeVisible();
    clock.mockReturnValue(2000);
    await act(() => vi.advanceTimersByTime(2000));
    expect(screen.getByText('00:00:39 elapsed')).toBeVisible();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  it('distinguishes cancellation and translates feedback', async () => {
    await i18n.changeLanguage('es-ES');
    render(
      <ModelSetupProgress
        model={{ elapsedSeconds: 65, error: null, status: 'cancelling' }}
      />,
    );
    expect(screen.getByRole('status')).toHaveTextContent(
      'Cancelando la preparación del modelo…',
    );
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });
});
