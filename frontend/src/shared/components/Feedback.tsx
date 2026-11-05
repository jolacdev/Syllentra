import toast, { ToastBar, Toaster } from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import type { ReactNode } from 'react';

import { cn } from '@utils/cn';

import Icon from './Icon';

/** Float dismissible feedback without moving the workspace or stealing keyboard focus. */
export const Notifications = () => {
  const { t } = useTranslation();
  return (
    <Toaster
      position="bottom-right"
      toastOptions={{
        duration: 4000,
        error: { duration: Infinity },
        style: {
          background: 'var(--surface)',
          border: '1px solid color-mix(in srgb, var(--ink) 15%, transparent)',
          borderRadius: 12,
          color: 'var(--ink)',
          fontSize: 14,
          maxWidth: 400,
          padding: 12,
        },
      }}
    >
      {(notification) => (
        <ToastBar toast={notification}>
          {({ message }) => (
            <>
              <Icon
                className={cn(
                  'size-5 shrink-0',
                  notification.type === 'error' ? 'text-danger' : 'text-accent',
                )}
                name={
                  notification.type === 'success'
                    ? 'check'
                    : 'information-outline'
                }
              />
              <div className="min-w-0 flex-1 break-words">{message}</div>
              <button
                aria-label={t('common.dismissNotification')}
                className="text-ink/70 hover:bg-ink/5 self-start rounded-lg p-1.5"
                type="button"
                onClick={() => toast.dismiss(notification.id)}
              >
                <Icon className="size-4" name="close" />
              </button>
            </>
          )}
        </ToastBar>
      )}
    </Toaster>
  );
};

type NoticeProps = {
  children: ReactNode;
  isError?: boolean;
  onDismiss?: () => void;
};

/** Present feedback in the document flow so it stays discoverable. */
export const Notice = ({
  children,
  onDismiss = undefined,
  isError = false,
}: NoticeProps) => {
  const { t } = useTranslation();
  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-xl border p-4 text-sm',
        isError
          ? 'border-danger/25 bg-danger/10 text-danger'
          : 'border-ink/12 bg-surface text-ink/70',
      )}
      role={isError ? 'alert' : 'status'}
    >
      <Icon className="mt-0.5 size-4 shrink-0" name="information-outline" />
      <div className="min-w-0 flex-1 break-words">{children}</div>
      {onDismiss && (
        <button
          aria-label={t('common.dismiss')}
          className="rounded p-0.5"
          type="button"
          onClick={onDismiss}
        >
          <Icon className="size-4" name="close" />
        </button>
      )}
    </div>
  );
};
