import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import toast from 'react-hot-toast';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import App from '../../App';
import i18n from '../../i18n/i18n';
import { createPyWebViewMock } from '../../mocks/mockPyWebView';

/** Install an explicit simulated bridge and render the production workspace composition. */
const setup = async (scenario = 'ready') => {
  window.history.replaceState({}, '', `?preview=${scenario}`);
  Object.defineProperty(window, 'pywebview', {
    configurable: true,
    value: undefined,
    writable: true,
  });
  createPyWebViewMock();
  render(<App />);
  await screen.findByRole('heading', { name: 'Batch transcription' });
};

beforeEach(async () => {
  await i18n.changeLanguage('en');
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
  });
});

afterEach(async () => {
  cleanup();
  const batch = window.pywebview?.state.app.batch;
  if (batch?.status === 'running') {
    await window.pywebview.api.stop_batch(batch.id);
  }
  if (vi.isFakeTimers()) {
    vi.clearAllTimers();
    vi.useRealTimers();
  }
  toast.remove();
});

describe('batch workspace', () => {
  it('starts empty with SRT and beside-source defaults', async () => {
    /** Verify a fresh batch does not inherit an unexpected format or destination. */
    await setup('empty');
    expect(screen.getByRole('checkbox', { name: 'SRT' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'TXT' })).not.toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'VTT' })).not.toBeChecked();
    expect(
      screen.getByRole('radio', { name: 'Beside source files' }),
    ).toBeChecked();
    expect(
      screen.getByRole('button', { name: 'Start 0 files' }),
    ).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Add folder' })).toBeEnabled();
  });

  it('starts a new batch from the import toolbar and resets its export choices', async () => {
    /** The reset belongs with list management and must preserve a clear empty-batch result. */
    await setup();
    const reset = screen.getByRole('button', { name: 'New batch' });
    expect(
      screen.getByRole('button', { name: 'Add files' }).parentElement,
    ).toContainElement(reset);
    expect(reset).toHaveAttribute(
      'title',
      expect.stringContaining('reset export choices'),
    );
    fireEvent.click(screen.getByRole('checkbox', { name: 'TXT' }));
    await waitFor(() =>
      expect(screen.getByRole('checkbox', { name: 'TXT' })).toBeChecked(),
    );
    fireEvent.click(reset);
    await screen.findByRole('button', { name: 'Start 0 files' });
    expect(screen.getByRole('checkbox', { name: 'SRT' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'TXT' })).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'New batch' })).toBeDisabled();
  });

  it('uses one tri-state inclusion model for extensions and the file tree', async () => {
    /** A bulk extension decision must update leaves and folder aggregates together. */
    await setup();
    const wav = screen.getByRole('checkbox', { name: /WAV/ });
    expect(wav).toBePartiallyChecked();
    expect(
      screen.getByRole('treeitem', { name: /Research interviews/ }),
    ).toHaveAttribute('aria-checked', 'mixed');
    fireEvent.click(wav);
    await waitFor(() =>
      expect(screen.getByRole('checkbox', { name: /WAV/ })).toBeChecked(),
    );
    expect(
      screen.getByRole('treeitem', { name: /Research interviews/ }),
    ).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByRole('button', { name: 'Start 6 files' })).toBeEnabled();
    fireEvent.click(screen.getByRole('checkbox', { name: /WAV/ }));
    await waitFor(() =>
      expect(screen.getByRole('checkbox', { name: /WAV/ })).not.toBeChecked(),
    );
    expect(
      screen.getByRole('treeitem', { name: /Episode 02/ }),
    ).toHaveAttribute('aria-checked', 'mixed');
  });

  it('keeps inspection and keyboard navigation independent from inclusion', async () => {
    /** Arrow navigation and Enter must not silently schedule or unschedule recordings. */
    await setup();
    const inclusion = vi.spyOn(window.pywebview.api, 'set_inclusion');
    const folder = screen.getByRole('treeitem', { name: /Episode 01/ });
    fireEvent.keyDown(folder, { key: 'ArrowRight' });
    const recording = screen.getByRole('treeitem', {
      name: /Interview with Elena/,
    });
    fireEvent.keyDown(recording, { key: 'Enter' });
    expect(
      screen.getByRole('heading', { name: 'Interview with Elena.mp3' }),
    ).toBeInTheDocument();
    expect(recording).toHaveAttribute('aria-selected', 'true');
    expect(inclusion).not.toHaveBeenCalled();
    fireEvent.keyDown(recording, { key: 'Home' });
    expect(
      screen.getByRole('treeitem', { name: /Research interviews/ }),
    ).toHaveFocus();
    fireEvent.keyDown(recording, { key: ' ' });
    await waitFor(() =>
      expect(
        screen.getByRole('treeitem', { name: /Interview with Elena/ }),
      ).toHaveAttribute('aria-checked', 'false'),
    );
    expect(
      screen.getByRole('treeitem', { name: /Episode 01/ }),
    ).toHaveAttribute('aria-checked', 'mixed');
  });

  it('disables admission when every format is unchecked', async () => {
    /** Empty output configuration must be visible and actionable before preflight. */
    await setup();
    fireEvent.click(screen.getByRole('checkbox', { name: 'SRT' }));
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: 'Start 5 files' }),
      ).toBeDisabled(),
    );
    expect(screen.getByText('Select at least one format.')).toBeInTheDocument();
  });

  it('uses the native destination command and retains explicit destination mode', async () => {
    /** Choosing a custom folder must preserve formats and use a single native folder action. */
    await setup();
    const choose = vi.spyOn(window.pywebview.api, 'choose_destination');
    fireEvent.click(screen.getByRole('radio', { name: 'Custom folder' }));
    await waitFor(() =>
      expect(
        screen.getByRole('radio', { name: 'Custom folder' }),
      ).toBeChecked(),
    );
    expect(choose).toHaveBeenCalledOnce();
    expect(screen.getByText('/Preview/Exports')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'SRT' })).toBeChecked();
  });

  it('reviews existing outputs before admitting inference', async () => {
    /** A conflict modal must show concrete paths and wait for an explicit decision. */
    await setup('conflicts');
    const start = vi.spyOn(window.pywebview.api, 'start_batch');
    const resolve = vi.spyOn(window.pywebview.api, 'resolve_conflicts');
    fireEvent.click(screen.getByRole('button', { name: 'Start 5 files' }));
    const dialog = await screen.findByRole('dialog', {
      name: '1 output already exists',
    });
    expect(start).not.toHaveBeenCalled();
    expect(
      within(dialog).getByText(
        /Research interviews\/Episode 01\/Interview with Elena.srt/,
      ),
    ).toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText('Apply to all conflicts'), {
      target: { value: 'rename' },
    });
    fireEvent.click(
      within(dialog).getByRole('button', { name: 'Start batch' }),
    );
    await waitFor(() => expect(start).toHaveBeenCalledOnce());
    expect(resolve).toHaveBeenCalledWith(
      expect.any(String),
      expect.any(Array),
      'rename',
    );
    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
    );
  });

  it('shows current-recording progress separately from completed batch items', async () => {
    /** A single active recording must show its supplied percentage before any file has finished. */
    await setup();
    vi.useFakeTimers();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Start 5 files' }));
      await vi.advanceTimersByTimeAsync(350);
    });
    expect(
      screen.getByRole('progressbar', { name: 'Transcription progress' }),
    ).toHaveAttribute('value', '50');
    expect(
      screen.getByRole('progressbar', { name: 'Batch progress' }),
    ).toHaveAttribute('value', '0');
    expect(
      screen.getByRole('region', { name: 'Transcription progress' }),
    ).toHaveTextContent('50%');
    expect(screen.getAllByRole('progressbar')).toHaveLength(2);
    await act(async () => vi.advanceTimersByTimeAsync(10_000));
    expect(
      screen.queryByRole('progressbar', { name: 'Transcription progress' }),
    ).not.toBeInTheDocument();
  });

  it('keeps the queue visible and opens read-only completed results without navigation', async () => {
    /** Automatic exports must remain attached to the inspected source and expose native file actions. */
    await setup();
    vi.useFakeTimers();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Start 5 files' }));
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(screen.getByText('Batch finished')).toBeInTheDocument();
    const summary = screen.getByRole('group', { name: 'Batch results' });
    expect(within(summary).getByText('Time spent 00:00:07')).toBeVisible();
    expect(
      screen.getByRole('tree', { name: 'Recordings' }),
    ).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(screen.getByRole('treeitem', { name: /Opening notes/ }));
    });
    expect(
      screen.getByText('This is a simulated transcript.'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Duration 00:00:24 · Processing time 00:00:01'),
    ).toBeVisible();
    expect(
      screen.getByRole('button', { name: 'Open SRT output' }),
    ).toBeEnabled();
    expect(
      screen.getByRole('button', { name: 'Reveal SRT output' }),
    ).toBeEnabled();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Copy text' }));
    });
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining(
        'Completed transcripts are exported automatically',
      ),
    );
  });

  it('expands the transcript into a wide dialog and returns to the batch', async () => {
    /** A completed preview must be readable in a wider space without leaving the queue. */
    await setup();
    vi.useFakeTimers();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Start 5 files' }));
      await vi.advanceTimersByTimeAsync(10_000);
    });
    await act(async () =>
      fireEvent.click(screen.getByRole('treeitem', { name: /Opening notes/ })),
    );
    await act(async () => {
      fireEvent.click(
        screen.getByRole('button', { name: 'Expand transcript preview' }),
      );
    });
    const dialog = screen.getByRole('dialog', { name: 'Transcript preview' });
    expect(
      within(dialog).getByText('This is a simulated transcript.'),
    ).toBeInTheDocument();
    fireEvent.click(
      within(dialog).getByRole('button', { name: 'Close expanded preview' }),
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(
      screen.getByRole('tree', { name: 'Recordings' }),
    ).toBeInTheDocument();
  });

  it('uses one conflict decision per recording for all selected formats', async () => {
    /** A shared rename must have one control and resolve the complete conflicting format set. */
    await setup('conflicts');
    fireEvent.click(screen.getByRole('checkbox', { name: 'TXT' }));
    await waitFor(() =>
      expect(screen.getByRole('checkbox', { name: 'TXT' })).toBeChecked(),
    );
    fireEvent.click(screen.getByRole('checkbox', { name: 'VTT' }));
    await waitFor(() =>
      expect(screen.getByRole('checkbox', { name: 'VTT' })).toBeChecked(),
    );
    const resolve = vi.spyOn(window.pywebview.api, 'resolve_conflicts');
    fireEvent.click(screen.getByRole('button', { name: 'Start 5 files' }));
    const dialog = await screen.findByRole('dialog', {
      name: '3 outputs already exist',
    });
    const choice = within(dialog).getByLabelText(/Action for/);
    expect(within(dialog).getAllByRole('combobox')).toHaveLength(2);
    fireEvent.change(choice, { target: { value: 'rename' } });
    fireEvent.click(
      within(dialog).getByRole('button', { name: 'Start batch' }),
    );
    await waitFor(() => expect(resolve).toHaveBeenCalled());
    expect(resolve.mock.calls[0][1]).toHaveLength(3);
  });

  it('supports stopping active and queued work through the backend command', async () => {
    /** Stop must settle the queue while preserving its rows and cancellation outcomes. */
    await setup();
    const stop = vi.spyOn(window.pywebview.api, 'stop_batch');
    fireEvent.click(screen.getByRole('button', { name: 'Start 5 files' }));
    await screen.findByRole('button', { name: 'Stop batch' });
    fireEvent.click(screen.getByRole('button', { name: 'Stop batch' }));
    await screen.findByText('Batch stopped');
    expect(stop).toHaveBeenCalledOnce();
    expect(
      screen.getByRole('tree', { name: 'Recordings' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Retry failed / cancelled' }),
    ).toBeEnabled();
  });

  it('keeps transcription running until quit is confirmed and shows stopping feedback', async () => {
    /** Native close requests must offer a safe way back and prevent repeated quit commands. */
    await setup();
    const api = window.pywebview.api;
    const keep = vi.spyOn(api, 'keep_open');
    let finishQuit = () => {};
    const quit = vi.spyOn(api, 'quit_app').mockImplementation(
      () =>
        new Promise((resolve) => {
          finishQuit = () => resolve({ error: null });
        }),
    );
    fireEvent.click(screen.getByRole('button', { name: 'Start 5 files' }));
    await screen.findByRole('button', { name: 'Stop batch' });
    await act(async () => {
      window.pywebview.state.app.closeRequested = true;
      await api.set_appearance('system', 'en');
    });
    let dialog = await screen.findByRole('dialog', {
      name: 'Close Syllentra?',
    });
    expect(within(dialog).getByText(/Active work will stop/)).toBeVisible();
    expect(quit).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Keep open' }));
    await waitFor(() => expect(dialog).not.toBeInTheDocument());
    expect(keep).toHaveBeenCalledOnce();
    expect(window.pywebview.state.app.batch.status).toBe('running');
    await act(async () => {
      window.pywebview.state.app.closeRequested = true;
      await api.set_appearance('system', 'en');
    });
    dialog = await screen.findByRole('dialog', { name: 'Close Syllentra?' });
    fireEvent.click(
      within(dialog).getByRole('button', { name: 'Stop & quit' }),
    );
    expect(
      within(dialog).getByRole('button', { name: 'Stopping…' }),
    ).toBeDisabled();
    expect(
      within(dialog).getByRole('button', { name: 'Keep open' }),
    ).toBeDisabled();
    fireEvent(dialog, new Event('cancel', { cancelable: true }));
    expect(keep).toHaveBeenCalledOnce();
    expect(quit).toHaveBeenCalledOnce();
    await act(async () => finishQuit());
  });

  it('shows engine-owned spoken-language coverage in settings', async () => {
    /** Model coverage must be discoverable independently of the interface language setting. */
    await setup();
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }));
    const dialog = await screen.findByRole('dialog', { name: 'Settings' });
    expect(within(dialog).getByText('Application data folder')).toBeVisible();
    expect(within(dialog).getByText('/Preview/Syllentra Data')).toBeVisible();
    fireEvent.click(
      within(dialog).getByText('Supported spoken languages (25)'),
    );
    expect(within(dialog).getByText('Greek')).toBeVisible();
    expect(within(dialog).getByText('Maltese')).toBeVisible();
    expect(within(dialog).getByText(/Japanese is not supported/)).toBeVisible();
    expect(
      within(dialog).getByText(/The list comes from the active engine/),
    ).toBeVisible();
  });

  it('restores focus when settings close and translates the complete workspace', async () => {
    /** Native dialog semantics and locale changes must preserve an actionable workspace. */
    await setup();
    const trigger = screen.getByRole('button', { name: 'Settings' });
    trigger.focus();
    fireEvent.click(trigger);
    const dialog = screen.getByRole('dialog', { name: 'Settings' });
    fireEvent.change(within(dialog).getByLabelText('Interface language'), {
      target: { value: 'es-ES' },
    });
    await screen.findByRole('heading', { name: 'Transcripción por lotes' });
    fireEvent.click(screen.getByRole('button', { name: 'Listo' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ajustes' })).toHaveFocus();
    expect(
      screen.getByRole('button', { name: 'Iniciar 5 archivos' }),
    ).toBeEnabled();
  });

  it('requires an explicit setup command when the model is missing', async () => {
    /** Import remains possible while missing weights must never trigger an implicit download. */
    window.history.replaceState({}, '', '?preview');
    Object.defineProperty(window, 'pywebview', {
      configurable: true,
      value: undefined,
      writable: true,
    });
    createPyWebViewMock();
    const setupModel = vi.spyOn(window.pywebview.api, 'setup_model');
    render(<App />);
    await screen.findByRole('button', { name: 'Download & prepare' });
    expect(setupModel).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Add folder' })).toBeEnabled();
    vi.useFakeTimers();
    await act(async () => {
      fireEvent.click(
        screen.getByRole('button', { name: 'Download & prepare' }),
      );
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(setupModel).toHaveBeenCalledOnce();
    expect(
      screen.queryByRole('button', { name: 'Download & prepare' }),
    ).not.toBeInTheDocument();
  });

  it('shows model setup feedback and allows cancelling the download', async () => {
    /** Preparation disables conflicting edits while keeping visible feedback and cancellation available. */
    window.history.replaceState({}, '', '?preview');
    Object.defineProperty(window, 'pywebview', {
      configurable: true,
      value: undefined,
      writable: true,
    });
    createPyWebViewMock();
    render(<App />);
    await screen.findByRole('button', { name: 'Download & prepare' });
    vi.useFakeTimers();
    await act(async () => {
      fireEvent.click(
        screen.getByRole('button', { name: 'Download & prepare' }),
      );
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    expect(
      screen.getByText('Downloading and preparing the model…'),
    ).toBeVisible();
    expect(screen.getByRole('button', { name: 'Add files' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeEnabled();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(
      screen.queryByText('Downloading and preparing the model…'),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Download & prepare' }),
    ).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Add files' })).toBeEnabled();
  });
});

describe('workspace recovery', () => {
  it('retries a failed initial collection read', async () => {
    /** A transient bridge failure must expose an action that completes hydration. */
    window.history.replaceState({}, '', '?preview=ready');
    Object.defineProperty(window, 'pywebview', {
      configurable: true,
      value: undefined,
      writable: true,
    });
    createPyWebViewMock();
    vi.spyOn(window.pywebview.api, 'get_workspace').mockRejectedValueOnce(
      new Error('Disconnected'),
    );
    render(<App />);
    expect(
      await screen.findByText('Your workspace could not be opened.'),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(
      await screen.findByRole('heading', { name: 'Batch transcription' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start 5 files' })).toBeEnabled();
  });
});
