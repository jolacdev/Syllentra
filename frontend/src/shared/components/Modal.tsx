import { useEffect, useId, useRef } from 'react';
import type { ReactNode } from 'react';

import { cn } from '@utils/cn';

import Button from './Button';

type ModalProps = {
  initialFocusId?: string;
  children: ReactNode;
  title: string;
  closeLabel?: string;
  isDismissible?: boolean;
  isWide?: boolean;
  onClose: () => void;
};

/** Give workflow dialogs native focus trapping, Escape handling, and focus restoration. */
const Modal = ({
  initialFocusId = undefined,
  children,
  closeLabel = undefined,
  onClose,
  title,
  isDismissible = true,
  isWide = false,
}: ModalProps) => {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const previous = document.activeElement;
    const element = dialog.current;
    element?.showModal();
    if (initialFocusId) {
      document.getElementById(initialFocusId)?.focus();
    }
    return () => {
      element?.close();
      if (previous instanceof HTMLElement && previous.isConnected) {
        previous.focus();
      }
    };
  }, [initialFocusId]);
  return (
    <dialog
      ref={dialog}
      aria-labelledby={titleId}
      className={cn(
        'border-ink/15 bg-surface text-ink backdrop:bg-ink/40 m-auto max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] rounded-2xl border shadow-xl',
        isWide
          ? 'h-[calc(100dvh-2rem)] max-w-[1200px] grid-rows-[auto_minmax(0,1fr)] overflow-hidden open:grid'
          : 'max-w-2xl overflow-y-auto p-6',
      )}
      onCancel={(event) => {
        event.preventDefault();
        if (isDismissible) {
          onClose();
        }
      }}
    >
      <header
        className={cn(
          'flex items-center justify-between gap-3',
          isWide && 'border-ink/10 border-b px-4 py-2 sm:px-6',
        )}
      >
        <h2 className="text-xl font-semibold tracking-tight" id={titleId}>
          {title}
        </h2>
        {closeLabel && (
          <Button
            aria-label={closeLabel}
            className="size-10 shrink-0 p-0"
            icon="close"
            title={closeLabel}
            variant="ghost"
            onClick={onClose}
          />
        )}
      </header>
      {children}
    </dialog>
  );
};

export default Modal;
