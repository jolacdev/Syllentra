import { useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import Button from '@components/Button';
import Icon from '@components/Icon';
import { cn } from '@utils/cn';
import type { MediaItem } from 'types/pywebview/pywebview-api';

type AudioGroup = 'default' | 'override' | 'preferred' | 'single';

/** Classify the effective selection rule, combining both automatic default routes. */
const groupFor = ({ audio }: MediaItem) =>
  audio.reason === 'fallback' ? 'default' : audio.reason;

type AudioTrackSummaryProps = {
  inspectedId: null | string;
  items: MediaItem[];
  preferredLanguage: null | string;
  onInspect: (id: string) => void;
  onOpenSettings: () => void;
};

/** Summarize automatic choices for the entire selection without requiring individual confirmations. */
const AudioTrackSummary = ({
  inspectedId,
  items,
  onInspect,
  onOpenSettings,
  preferredLanguage,
}: AudioTrackSummaryProps) => {
  const { t } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(true);
  const contentId = useId();
  const selectedRow = useRef<HTMLLIElement>(null);
  const language = preferredLanguage
    ? t(`batch.spokenLanguages.${preferredLanguage}`, {
        defaultValue: preferredLanguage,
      })
    : t('audio.defaultSelection');
  const selected = items.filter((item) => item.isIncluded && item.isAvailable);
  const unavailable = selected.filter(
    (item) => item.audio.reason === 'unavailable',
  );
  const inspected = selected.find((item) => item.id === inspectedId);
  const inspectedGroup = inspected ? groupFor(inspected) : null;
  const [openGroups, setOpenGroups] = useState<
    Partial<Record<AudioGroup, boolean>>
  >({});
  useEffect(() => {
    const row = selectedRow.current;
    const list = row?.parentElement;
    if (!row || !list || row.closest('[hidden]')) {
      return;
    }
    // Scroll only the file list: the inspector and keyboard focus stay where the user is working.
    if (row.offsetTop < list.scrollTop) {
      list.scrollTop = row.offsetTop;
    } else if (
      row.offsetTop + row.offsetHeight >
      list.scrollTop + list.clientHeight
    ) {
      list.scrollTop = row.offsetTop + row.offsetHeight - list.clientHeight;
    }
  }, [inspectedId, inspectedGroup, isExpanded, openGroups]);
  const groups = [
    { hint: 'singleHint', key: 'single', title: 'single' },
    {
      hint: preferredLanguage ? 'preferredHint' : 'preferredUnsetHint',
      key: 'preferred',
      title: preferredLanguage ? 'preferred' : 'preferredUnset',
    },
    {
      hint: preferredLanguage ? 'fallbackHint' : 'defaultHint',
      key: 'default',
      title: 'default',
    },
    { hint: 'manualHint', key: 'override', title: 'manual' },
  ] as const;
  return (
    <section className="border-ink/10 shrink-0 border-b">
      <h2>
        <button
          aria-controls={contentId}
          aria-expanded={isExpanded}
          className="flex w-full items-center gap-2 px-5 py-4 text-left text-sm font-semibold"
          type="button"
          onClick={() => setIsExpanded((previous) => !previous)}
        >
          <Icon
            className={cn('text-ink/65 size-3.5', isExpanded && 'rotate-90')}
            name="chevron-right"
          />
          <span className="min-w-0 flex-1">{t('audio.selectionSummary')}</span>{' '}
          <span
            className="text-ink/65 ml-auto max-w-28 truncate text-xs font-normal"
            title={language}
          >
            {language}
          </span>
        </button>
      </h2>
      <div className="px-5 pb-4" hidden={!isExpanded} id={contentId}>
        <p className="text-ink/65 text-xs leading-5">
          {t(
            preferredLanguage ? 'audio.activePreference' : 'audio.noPreference',
            { language },
          )}
        </p>
        <Button
          className="text-accent mt-1 min-h-8 px-0 text-xs"
          variant="ghost"
          onClick={onOpenSettings}
        >
          {t('audio.changePreference')}
        </Button>
        <div className="mt-2 space-y-2">
          {groups.map((group) => {
            const isOpen = !!openGroups[group.key];
            const groupId = `${contentId}-${group.key}`;
            const title = t(`audio.groups.${group.title}`, { language });
            const files = selected.filter(
              (item) => groupFor(item) === group.key,
            );
            return (
              <div key={group.key} className="border-ink/10 rounded-lg border">
                <h3>
                  <button
                    aria-controls={groupId}
                    aria-expanded={isOpen}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-semibold"
                    type="button"
                    onClick={() =>
                      setOpenGroups((current) => ({
                        ...current,
                        [group.key]: !current[group.key],
                      }))
                    }
                  >
                    <Icon
                      className={cn(
                        'text-ink/65 size-3 shrink-0',
                        isOpen && 'rotate-90',
                      )}
                      name="chevron-right"
                    />
                    <span>{title}</span>{' '}
                    <span className="text-ink/65 ml-auto tabular-nums">
                      {files.length}
                    </span>
                  </button>
                </h3>
                <div
                  aria-label={title}
                  className="px-3 pb-2"
                  hidden={!isOpen}
                  id={groupId}
                  role="region"
                >
                  <p className="text-ink/65 mb-2 text-xs leading-5">
                    {t(`audio.groups.${group.hint}`, { language })}
                  </p>
                  {files.length === 0 && (
                    <p className="text-ink/65 text-xs leading-5">
                      {t('audio.groups.empty')}
                    </p>
                  )}
                  {isOpen && files.length > 0 && (
                    <ul className="relative max-h-40 space-y-1 overflow-y-auto">
                      {files.map((item) => (
                        <li
                          key={item.id}
                          ref={
                            item.id === inspectedId ? selectedRow : undefined
                          }
                        >
                          <Button
                            aria-current={
                              item.id === inspectedId ? 'true' : undefined
                            }
                            aria-label={item.relativePath}
                            className={cn(
                              'min-h-8 w-full justify-start px-2 py-1 text-left text-xs font-normal',
                              item.id === inspectedId &&
                                'bg-accent/10 text-accent hover:bg-accent/15 hover:text-accent',
                            )}
                            title={item.path}
                            variant="ghost"
                            onClick={() => onInspect(item.id)}
                          >
                            <span className="min-w-0">
                              <span className="block truncate">
                                {item.name}
                              </span>
                              {item.relativePath !== item.name && (
                                <span className="text-ink/65 block truncate text-[10px]">
                                  {item.relativePath}
                                </span>
                              )}
                            </span>
                          </Button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            );
          })}
          {unavailable.length > 0 && (
            <p className="text-ink/65 text-xs leading-5">
              {t('audio.unavailableCount', { count: unavailable.length })}
            </p>
          )}
        </div>
      </div>
    </section>
  );
};

export default AudioTrackSummary;
