import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { KeyboardEvent, MouseEvent } from 'react';

import Icon from '@components/Icon';
import { cn } from '@utils/cn';
import { formatSizeUnit } from '@utils/formatSizeUnit';

import { buildTree, selectionState, visibleTree } from './tree';
import type { MediaNode } from './tree';
import type { Workspace } from './types';

type MediaTreeProps = {
  inspectedId: null | string;
  workspace: Workspace;
  isDisabled: boolean;
  onInclude: (ids: string[], included: boolean) => void;
  onInspect: (id: string) => void;
};

/** Keep hierarchy, checkbox inclusion, keyboard focus, and transcript inspection independent. */
const MediaTree = ({
  inspectedId,
  onInclude,
  onInspect,
  workspace,
  isDisabled,
}: MediaTreeProps) => {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [focusedId, setFocusedId] = useState<null | string>(null);
  const nodes = useMemo(() => buildTree(workspace), [workspace]);
  const rows = useMemo(() => visibleTree(nodes, expanded), [nodes, expanded]);
  const included = useMemo(
    () =>
      new Set(
        workspace.items
          .filter((item) => item.isIncluded)
          .map((item) => item.id),
      ),
    [workspace],
  );
  const tabStop = rows.some((node) => node.id === focusedId)
    ? focusedId
    : rows[0]?.id;

  /** Toggle one branch without changing which recordings are included. */
  const toggle = (node: MediaNode) => {
    setExpanded((previous) => ({
      ...previous,
      [node.id]: !(previous[node.id] ?? node.parentId === null),
    }));
  };

  /** Move the tree's single keyboard stop to an existing visible row. */
  const focus = (id: string | undefined) => {
    if (id) {
      document.getElementById(`media-${id}`)?.focus();
    }
  };

  /** Apply group inclusion to eligible leaves through the same backend command as individual files. */
  const include = (node: MediaNode) => {
    if (!isDisabled && node.itemIds.length) {
      onInclude(node.itemIds, selectionState(node.itemIds, included) !== true);
    }
  };

  /** Implement the documented tree navigation model without changing inclusion on arrow keys. */
  const keyDown = (event: KeyboardEvent<HTMLDivElement>, node: MediaNode) => {
    const index = rows.findIndex((row) => row.id === node.id);
    const isExpanded = expanded[node.id] ?? node.parentId === null;
    switch (event.key) {
      case 'ArrowDown':
        focus(rows[index + 1]?.id);
        break;
      case 'ArrowUp':
        focus(rows[index - 1]?.id);
        break;
      case 'Home':
        focus(rows[0]?.id);
        break;
      case 'End':
        focus(rows[rows.length - 1]?.id);
        break;
      case 'ArrowRight':
        if (!node.item && !isExpanded) {
          toggle(node);
        } else if (!node.item) {
          focus(rows[index + 1]?.id);
        }
        break;
      case 'ArrowLeft':
        if (!node.item && isExpanded) {
          toggle(node);
        } else {
          focus(node.parentId ?? undefined);
        }
        break;
      case ' ':
        include(node);
        break;
      case 'Enter':
        if (node.item) {
          onInspect(node.item.id);
        } else {
          toggle(node);
        }
        break;
      default:
        return;
    }
    event.preventDefault();
  };

  /** Distinguish checkbox hit targets from row inspection and folder disclosure. */
  const click = (event: MouseEvent<HTMLDivElement>, node: MediaNode) => {
    event.currentTarget.focus();
    if (
      event.target instanceof Element &&
      event.target.closest('[data-inclusion]')
    ) {
      include(node);
    } else if (node.item) {
      onInspect(node.item.id);
    } else {
      toggle(node);
    }
  };

  return (
    <div
      aria-label={t('batch.files')}
      aria-multiselectable="true"
      className="min-h-0 flex-1 overflow-auto px-2 pb-3 outline-none"
      role="tree"
    >
      {rows.map((node) => {
        const item = node.item;
        const checked = selectionState(node.itemIds, included);
        const count = node.itemIds.filter((id) => included.has(id)).length;
        const isExpanded = expanded[node.id] ?? node.parentId === null;
        return (
          <div
            key={node.id}
            aria-checked={checked}
            aria-expanded={item ? undefined : isExpanded}
            aria-level={node.depth + 1}
            aria-posinset={node.position}
            aria-selected={item ? item.id === inspectedId : false}
            aria-setsize={node.siblingCount}
            className={cn(
              'group my-0.5 flex min-h-11 cursor-default items-center gap-2 rounded-lg py-2 pr-3 text-sm outline-offset-[-2px] transition-colors',
              item?.id === inspectedId ? 'bg-accent/9' : 'hover:bg-ink/4',
              item && !item.isIncluded && 'text-ink/65',
            )}
            id={`media-${node.id}`}
            role="treeitem"
            style={{ paddingInlineStart: 10 + node.depth * 18 }}
            tabIndex={node.id === tabStop ? 0 : -1}
            onClick={(event) => click(event, node)}
            onFocus={() => setFocusedId(node.id)}
            onKeyDown={(event) => keyDown(event, node)}
          >
            <span
              aria-hidden="true"
              className="text-ink/65 grid size-4 shrink-0 place-items-center"
            >
              {!item && (
                <Icon
                  className={cn('size-3.5', isExpanded && 'rotate-90')}
                  name="chevron-right"
                />
              )}
            </span>
            <span
              aria-hidden="true"
              className={cn(
                'grid size-4 shrink-0 place-items-center rounded border',
                checked
                  ? 'border-accent bg-accent text-canvas'
                  : 'border-ink/55 bg-surface',
                (!node.itemIds.length || isDisabled) && 'opacity-45',
              )}
              data-inclusion=""
            >
              {checked && (
                <Icon
                  className="size-3"
                  name={checked === 'mixed' ? 'minus' : 'check'}
                />
              )}
            </span>
            <Icon
              className={cn(
                'text-ink/65 ml-1 size-4 shrink-0',
                !item && 'text-accent/80',
              )}
              name={item ? 'file-document-outline' : 'folder-outline'}
            />
            <span
              className={cn('min-w-16 flex-1 truncate', !item && 'font-medium')}
              title={node.path}
            >
              {node.name}
            </span>
            {item ? (
              <>
                <span className="text-ink/65 hidden shrink-0 text-xs tabular-nums xl:block">
                  {formatSizeUnit(item.size)}
                </span>
                <span
                  className={cn(
                    'w-24 shrink-0 truncate text-right text-xs',
                    item.status === 'failed' || !item.isAvailable
                      ? 'text-danger'
                      : item.status === 'completed'
                        ? 'text-accent'
                        : 'text-ink/65',
                  )}
                >
                  {t(
                    `batch.status.${!item.isAvailable ? 'unavailable' : item.noSpeech && item.status === 'completed' ? 'noSpeech' : item.status}`,
                  )}
                </span>
              </>
            ) : (
              <span className="text-ink/65 shrink-0 text-xs tabular-nums">
                {count} / {node.itemIds.length}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default MediaTree;
