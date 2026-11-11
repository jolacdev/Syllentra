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

/** Change the persistent audio preference through general Settings and return to the workspace. */
const setAudioPreference = async (language: string) => {
  fireEvent.click(screen.getByRole('button', { name: 'Settings' }));
  const dialog = await screen.findByRole('dialog', { name: 'Settings' });
  const preference = within(dialog).getByLabelText('Preferred audio language');
  fireEvent.change(preference, { target: { value: language } });
  await waitFor(() => expect(preference).toHaveValue(language));
  fireEvent.click(within(dialog).getByRole('button', { name: 'Done' }));
};

/** Scope file and explanation queries to a named audio group. */
const withinAudioGroup = (name: string) =>
  within(screen.getByRole('region', { name }));

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
  it('connects the audio accordion to its persistent setting and keeps the chosen language visible when collapsed', async () => {
    /** Explain the active rule, focus its setting directly, and reflect changes without losing disclosure state. */
    await setup();
    const toggle = screen.getByRole('button', {
      name: 'Audio track selection File default',
    });
    const explanation = screen.getByText(
      'No language preference is set. Files with multiple audio tracks use their default or first track.',
    );
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(explanation).toBeVisible();
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(explanation).not.toBeVisible();
    fireEvent.click(toggle);
    const change = screen.getByRole('button', {
      name: 'Change audio preference in Settings',
    });
    change.focus();
    fireEvent.click(change);
    const dialog = await screen.findByRole('dialog', { name: 'Settings' });
    const preference = within(dialog).getByLabelText(
      'Preferred audio language',
    );
    expect(preference).toHaveFocus();
    fireEvent.change(preference, { target: { value: 'en' } });
    await waitFor(() => expect(preference).toHaveValue('en'));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Done' }));
    expect(change).toHaveFocus();
    expect(toggle).toHaveAccessibleName('Audio track selection English');
    expect(
      screen.getByText(
        'Prefer English in files with multiple audio tracks. Files with one track use that track.',
      ),
    ).toBeVisible();
    fireEvent.click(toggle);
    await setAudioPreference('fr');
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(toggle).toHaveAccessibleName('Audio track selection French');
    await act(() => i18n.changeLanguage('es-ES'));
    expect(toggle).toHaveAccessibleName('Selección de pistas de audio Francés');
    fireEvent.click(toggle);
    expect(
      screen.getByRole('button', {
        name: 'Cambiar la preferencia de audio en Ajustes',
      }),
    ).toBeVisible();
  });

  it('applies the optional preference only to multi-track files and starts without selection prompts', async () => {
    /** Mixed single-track and multi-track recordings must keep automatic fallback without blocking admission. */
    await setup();
    expect(
      screen.queryByLabelText('Preferred audio language'),
    ).not.toBeInTheDocument();
    const choose = vi.spyOn(window.pywebview.api, 'set_audio_language');
    const start = vi.spyOn(window.pywebview.api, 'start_batch');
    await setAudioPreference('en');
    await screen.findByRole('button', { name: 'Default or first track 1' });
    expect(choose).toHaveBeenCalledWith('en');
    expect(
      screen.getByRole('button', { name: 'Single audio track 3' }),
    ).toHaveAttribute('aria-expanded', 'false');
    expect(
      screen.getByRole('button', { name: 'English matches 1' }),
    ).toHaveAttribute('aria-expanded', 'false');
    expect(
      screen.getByRole('button', { name: 'Default or first track 1' }),
    ).toHaveAttribute('aria-expanded', 'false');
    expect(
      screen.getByRole('button', { name: 'Manual selection 0' }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Transcribe 5 files' }));
    await waitFor(() => expect(start).toHaveBeenCalledOnce());
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }));
    expect(screen.getByLabelText('Preferred audio language')).toBeDisabled();
  });

  it('preserves disclosure choices and the inspected file when track changes move it between groups', async () => {
    /** Moving files updates counts without opening closed groups, closing empty ones, or stealing focus. */
    await setup();
    await setAudioPreference('en');
    const include = vi.spyOn(window.pywebview.api, 'set_inclusion');
    const choose = vi.spyOn(window.pywebview.api, 'select_audio_track');
    const defaults = screen.getByRole('button', {
      name: 'Default or first track 1',
    });
    expect(defaults).toHaveAttribute('aria-expanded', 'false');
    const preferred = screen.getByRole('button', { name: 'English matches 1' });
    fireEvent.click(preferred);
    fireEvent.click(
      withinAudioGroup('English matches').getByRole('button', {
        name: /Camera audio/,
      }),
    );
    const picker = await screen.findByLabelText('Audio track');
    expect(picker).toHaveValue('');
    expect(
      screen.getByText(/Track 2 · English · English dialogue/, {
        selector: 'p',
      }),
    ).toBeInTheDocument();
    picker.focus();
    fireEvent.change(picker, { target: { value: '2' } });
    const manual = await screen.findByRole('button', {
      name: 'Manual selection 1',
    });
    expect(choose).toHaveBeenCalledWith('file-1', 2);
    expect(manual).toHaveAttribute('aria-expanded', 'false');
    expect(
      screen.getByRole('button', { name: 'English matches 0' }),
    ).toHaveAttribute('aria-expanded', 'true');
    expect(
      withinAudioGroup('English matches').getByText('No files in this group.'),
    ).toBeVisible();
    expect(picker).toHaveFocus();
    expect(picker).toHaveValue('2');
    expect(
      screen.getByRole('heading', { name: 'Camera audio.mp4' }),
    ).toBeInTheDocument();
    fireEvent.click(manual);
    expect(
      withinAudioGroup('Manual selection').getByRole('button', {
        name: /Camera audio/,
      }),
    ).toHaveAttribute('aria-current', 'true');
    fireEvent.click(preferred);
    picker.focus();
    fireEvent.change(picker, { target: { value: '' } });
    await screen.findByRole('button', { name: 'Manual selection 0' });
    expect(choose).toHaveBeenLastCalledWith('file-1', null);
    expect(preferred).toHaveAccessibleName('English matches 1');
    expect(preferred).toHaveAttribute('aria-expanded', 'false');
    expect(manual).toHaveAttribute('aria-expanded', 'true');
    expect(
      withinAudioGroup('Manual selection').getByText('No files in this group.'),
    ).toBeVisible();
    expect(picker).toHaveFocus();
    fireEvent.change(picker, { target: { value: '2' } });
    await screen.findByRole('button', { name: 'Manual selection 1' });
    expect(manual).toHaveAttribute('aria-expanded', 'true');
    await setAudioPreference('fr');
    expect(picker).toHaveValue('2');
    expect(screen.getByText('Selected manually for this file.')).toBeVisible();
    picker.focus();
    fireEvent.change(picker, { target: { value: '' } });
    await screen.findByRole('button', { name: 'Manual selection 0' });
    expect(
      screen.getByText(
        'Preferred language unavailable or unknown; using the default or first audio track.',
      ),
    ).toBeVisible();
    expect(defaults).toHaveAttribute('aria-expanded', 'false');
    expect(picker).toHaveFocus();
    fireEvent.click(defaults);
    expect(
      withinAudioGroup('Default or first track').getByRole('button', {
        name: /Camera audio/,
      }),
    ).toHaveAttribute('aria-current', 'true');
    expect(include).not.toHaveBeenCalled();
    expect(
      screen.getByRole('button', { name: 'Transcribe 5 files' }),
    ).toBeEnabled();
  });

  it('explains every group and merges default choices and fallbacks into one count', async () => {
    /** File lists replace duplicate counters, keep empty categories, and stay independent of inclusion. */
    await setup();
    expect(
      screen.getByRole('button', { name: 'Default or first track 2' }),
    ).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(
      screen.getByRole('button', { name: 'Default or first track 2' }),
    );
    const defaults = withinAudioGroup('Default or first track');
    expect(defaults.getAllByRole('button')).toHaveLength(2);
    expect(
      defaults.getByText(
        'No language preference is set. These files use their marked default audio track, or their first audio track if none is marked.',
      ),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole('button', { name: 'Single audio track 3' }),
    );
    expect(
      withinAudioGroup('Single audio track').getAllByRole('button'),
    ).toHaveLength(3);
    await setAudioPreference('en');
    expect(
      screen.getByRole('button', { name: 'Default or first track 1' }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/File default: 0/)).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Manual selection 0' }),
    ).toBeInTheDocument();
  });

  it('keeps all four categories and their explanations available in an empty batch', async () => {
    /** Zero counts retain a stable layout, including a meaningful preferred-language label when none is set. */
    await setup('empty');
    for (const title of [
      'Single audio track',
      'Preferred language',
      'Default or first track',
      'Manual selection',
    ]) {
      const toggle = screen.getByRole('button', { name: `${title} 0` });
      expect(toggle).toHaveAttribute('aria-expanded', 'false');
      fireEvent.click(toggle);
      const group = withinAudioGroup(title);
      expect(group.getByText('No files in this group.')).toBeVisible();
      expect(group.queryByRole('list')).not.toBeInTheDocument();
    }
    expect(
      screen.getByText(
        'Set a preferred audio language in Settings. Files with a matching track will appear here.',
      ),
    ).toBeVisible();
  });

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
      screen.getByRole('button', { name: 'Transcribe 0 files' }),
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
    const includeLanguage = screen.getByRole('checkbox', {
      name: 'Include audio language in subtitle filenames',
    });
    expect(includeLanguage).not.toBeChecked();
    fireEvent.click(includeLanguage);
    await waitFor(() => expect(includeLanguage).toBeChecked());
    fireEvent.click(screen.getByRole('checkbox', { name: 'TXT' }));
    await waitFor(() =>
      expect(screen.getByRole('checkbox', { name: 'TXT' })).toBeChecked(),
    );
    fireEvent.click(reset);
    await screen.findByRole('button', { name: 'Transcribe 0 files' });
    expect(screen.getByRole('checkbox', { name: 'SRT' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'TXT' })).not.toBeChecked();
    expect(includeLanguage).not.toBeChecked();
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
    expect(
      screen.getByRole('button', { name: 'Transcribe 6 files' }),
    ).toBeEnabled();
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
      name: /Interview with Jane/,
    });
    fireEvent.keyDown(recording, { key: 'Enter' });
    expect(
      screen.getByRole('heading', { name: 'Interview with Jane.mp3' }),
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
        screen.getByRole('treeitem', { name: /Interview with Jane/ }),
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
        screen.getByRole('button', { name: 'Transcribe 5 files' }),
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
    const includeLanguage = screen.getByRole('checkbox', {
      name: 'Include audio language in subtitle filenames',
    });
    fireEvent.click(includeLanguage);
    await waitFor(() => expect(includeLanguage).toBeChecked());
    fireEvent.click(screen.getByRole('button', { name: 'Transcribe 5 files' }));
    const dialog = await screen.findByRole('dialog', {
      name: '1 output already exists',
    });
    expect(start).not.toHaveBeenCalled();
    expect(
      within(dialog).getByText(
        '/Preview/Research interviews/Episode 01/Interview with Jane.es.srt',
      ),
    ).toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText('Apply to all conflicts'), {
      target: { value: 'rename' },
    });
    fireEvent.click(
      within(dialog).getByRole('button', { name: 'Transcribe batch' }),
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
      fireEvent.click(
        screen.getByRole('button', { name: 'Transcribe 5 files' }),
      );
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
      fireEvent.click(
        screen.getByRole('button', { name: 'Transcribe 5 files' }),
      );
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
    expect(
      screen.getByText('Text copied to the clipboard.'),
    ).toBeInTheDocument();
  });

  it('retains completed results only while the effective audio track stays the same', async () => {
    /** Changing selection mode preserves speech, but another stream must clear the transcript and outputs. */
    await setup();
    vi.useFakeTimers();
    await act(async () => {
      fireEvent.click(
        screen.getByRole('button', { name: 'Transcribe 5 files' }),
      );
      await vi.advanceTimersByTimeAsync(10_000);
      fireEvent.click(screen.getByRole('treeitem', { name: /Opening notes/ }));
    });
    const picker = screen.getByLabelText('Audio track');
    await act(async () => fireEvent.change(picker, { target: { value: '0' } }));
    expect(screen.getByText('This is a simulated transcript.')).toBeVisible();
    expect(
      screen.getByRole('button', { name: 'Open SRT output' }),
    ).toBeEnabled();
    await act(async () => fireEvent.change(picker, { target: { value: '1' } }));
    expect(
      screen.queryByText('This is a simulated transcript.'),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Open SRT output' }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy text' })).toBeDisabled();
  });

  it('expands the transcript into a wide dialog and returns to the batch', async () => {
    /** A completed preview must be readable in a wider space without leaving the queue. */
    await setup();
    vi.useFakeTimers();
    await act(async () => {
      fireEvent.click(
        screen.getByRole('button', { name: 'Transcribe 5 files' }),
      );
      await vi.advanceTimersByTimeAsync(10_000);
    });
    await act(async () =>
      fireEvent.click(screen.getByRole('treeitem', { name: /Opening notes/ })),
    );
    const expand = screen.getByRole('button', {
      name: 'Expand transcript preview',
    });
    expand.focus();
    await act(async () => fireEvent.click(expand));
    const dialog = screen.getByRole('dialog', { name: 'Transcript preview' });
    const reader = within(dialog).getByRole('region', {
      name: 'Transcript preview',
    });
    expect(
      within(reader).getByText('This is a simulated transcript.'),
    ).toBeVisible();
    expect(
      within(dialog).getByRole('heading', {
        name: 'File details',
      }),
    ).toBeVisible();
    expect(
      within(dialog).getByRole('button', { name: 'Open SRT output' }),
    ).toBeVisible();
    const copy = within(dialog).getByRole('button', { name: 'Copy text' });
    const copyIcon = copy.querySelector('svg path')?.getAttribute('d');
    await act(async () => fireEvent.click(copy));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining('This is a simulated transcript.'),
    );
    expect(
      within(dialog).getByText('Text copied to the clipboard.'),
    ).toBeInTheDocument();
    expect(copy.querySelector('svg path')).toHaveAttribute('d', copyIcon);
    vi.mocked(navigator.clipboard.writeText).mockRejectedValueOnce(
      new Error('Clipboard unavailable'),
    );
    await act(async () => fireEvent.click(copy));
    expect(within(dialog).getByText('Could not copy')).toBeInTheDocument();
    fireEvent.click(
      within(dialog).getByRole('button', { name: 'Close expanded preview' }),
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(expand).toHaveFocus();
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
    fireEvent.click(screen.getByRole('button', { name: 'Transcribe 5 files' }));
    const dialog = await screen.findByRole('dialog', {
      name: '3 outputs already exist',
    });
    const choice = within(dialog).getByLabelText(/Action for/);
    expect(within(dialog).getAllByRole('combobox')).toHaveLength(2);
    fireEvent.change(choice, { target: { value: 'rename' } });
    fireEvent.click(
      within(dialog).getByRole('button', { name: 'Transcribe batch' }),
    );
    await waitFor(() => expect(resolve).toHaveBeenCalled());
    expect(resolve.mock.calls[0][1]).toHaveLength(3);
  });

  it('supports stopping active and queued work through the backend command', async () => {
    /** Stop must settle the queue while preserving its rows and cancellation outcomes. */
    await setup();
    const stop = vi.spyOn(window.pywebview.api, 'stop_batch');
    fireEvent.click(screen.getByRole('button', { name: 'Transcribe 5 files' }));
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
    fireEvent.click(screen.getByRole('button', { name: 'Transcribe 5 files' }));
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
    expect(within(dialog).getByText('Greek', { selector: 'li' })).toBeVisible();
    expect(
      within(dialog).getByText('Maltese', { selector: 'li' }),
    ).toBeVisible();
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
      screen.getByRole('button', { name: 'Transcribir 5 archivos' }),
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
    expect(
      screen.getByRole('button', { name: 'Transcribe 5 files' }),
    ).toBeEnabled();
  });
});
