import { useEffect, useId, useRef } from 'react';
import type { ReactNode } from 'react';

type ModalProps = {
  initialFocusId?: string;
  children: ReactNode;
  title: string;
  isDismissible?: boolean;
  isWide?: boolean;
  onClose: () => void;
};

/** Give workflow dialogs native focus trapping, Escape handling, and focus restoration. */
const Modal = ({
  initialFocusId = undefined,
  children,
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
      className="border-ink/15 bg-surface text-ink backdrop:bg-ink/40 m-auto max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-2xl overflow-y-auto rounded-2xl border p-6 shadow-xl"
      style={{ maxWidth: isWide ? 1200 : 672 }}
      onCancel={(event) => {
        event.preventDefault();
        if (isDismissible) {
          onClose();
        }
      }}
    >
      <h2 className="text-xl font-semibold tracking-tight" id={titleId}>
        {title}
      </h2>
      {children}
    </dialog>
  );
};

export default Modal;
