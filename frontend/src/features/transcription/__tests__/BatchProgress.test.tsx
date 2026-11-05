import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import type { BatchState } from 'types/pywebview/pywebview-api';

import i18n from '../../../i18n/i18n';
import BatchProgress from '../BatchProgress';

const batch: BatchState = {
  activeItemId: 'recording',
  id: 'batch',
  cancelled: 1,
  completed: 1,
  elapsedSeconds: 65,
  failed: 1,
  noSpeech: 0,
  phase: 'transcribing',
  progress: 50,
  skipped: 1,
  status: 'running',
  total: 5,
};
const item = { name: 'Episode.mkv', path: '/Recordings/Episode.mkv' };

beforeEach(async () => {
  await i18n.changeLanguage('en');
});
afterEach(cleanup);

describe('batch progress', () => {
  it('assigns the filename and phase to the current file and finished counts to the batch', () => {
    render(<BatchProgress batch={batch} item={item} />);
    const file = within(
      screen.getByRole('region', { name: 'Transcription progress' }),
    );
    const queue = within(
      screen.getByRole('region', { name: 'Batch progress' }),
    );

    expect(screen.getAllByRole('progressbar')).toHaveLength(2);
    expect(file.getByRole('progressbar')).toHaveAttribute('value', '50');
    expect(file.getByText('50%')).toBeVisible();
    expect(file.getByText('Episode.mkv')).toHaveAttribute('title', item.path);
    expect(file.getByRole('status')).toHaveTextContent('Transcribing…');
    expect(queue.queryByText('Episode.mkv')).not.toBeInTheDocument();
    expect(queue.getByRole('progressbar')).toHaveAttribute('value', '4');
    expect(queue.getByRole('progressbar')).toHaveAttribute('max', '5');
    expect(queue.getByText('80%')).toBeVisible();
    expect(queue.getByText('4 of 5 files finished')).toBeVisible();
    expect(queue.getByText('00:01:05 elapsed')).toBeVisible();
  });

  it.each([
    ['loading', 'Loading speech model…'],
    ['preparing', 'Reading audio…'],
    ['cancelling', 'Stopping current recording…'],
  ])('does not reuse another phase percentage while %s', (phase, status) => {
    render(
      <BatchProgress batch={{ ...batch, phase, progress: 95 }} item={item} />,
    );
    const file = within(
      screen.getByRole('region', { name: 'Transcription progress' }),
    );
    expect(screen.getAllByRole('progressbar')).toHaveLength(2);
    expect(file.getByRole('progressbar')).not.toHaveAttribute('value');
    expect(file.queryByText('95%')).not.toBeInTheDocument();
    expect(file.getByRole('status')).toHaveTextContent(status);
  });

  it('keeps transcription complete while outputs are still being saved', () => {
    render(
      <BatchProgress
        batch={{ ...batch, phase: 'exporting', progress: null }}
        item={item}
      />,
    );
    expect(
      screen.getByRole('progressbar', { name: 'Transcription progress' }),
    ).toHaveAttribute('value', '100');
    expect(screen.getByRole('status')).toHaveTextContent('Saving outputs…');
    expect(
      screen.getByRole('progressbar', { name: 'Batch progress' }),
    ).toHaveAttribute('value', '4');
  });

  it('avoids showing the previous recording percentage between files', () => {
    render(<BatchProgress batch={{ ...batch, progress: 100 }} item={null} />);
    const file = within(
      screen.getByRole('region', { name: 'Transcription progress' }),
    );
    expect(file.getByRole('progressbar')).not.toHaveAttribute('value');
    expect(file.getByText('Preparing the next recording…')).toBeVisible();
    expect(file.queryByRole('status')).not.toBeInTheDocument();
  });
});
