import type { MediaItem } from 'types/pywebview/pywebview-api';

import type { Workspace } from './types';

export type MediaNode = {
  id: string;
  parentId: null | string;
  children: MediaNode[];
  depth: number;
  item: MediaItem | null;
  itemIds: string[];
  name: string;
  path: string;
};

/** Compare siblings without changing the user's order of explicitly imported roots. */
const compareNodes = (left: MediaNode, right: MediaNode) =>
  Number(left.item !== null) - Number(right.item !== null) ||
  left.name.localeCompare(right.name, undefined, { numeric: true });

/** Keep folders before files while retaining a deterministic natural filename order. */
const sortChildren = (node: MediaNode) => {
  node.children.sort(compareNodes);
  node.children.forEach(sortChildren);
};

/** Build one hierarchy from source provenance without introducing another inclusion state. */
export const buildTree = (workspace: Workspace): MediaNode[] => {
  const nodes = new Map<string, MediaNode>();
  const roots: MediaNode[] = workspace.roots.map((root) => {
    const node: MediaNode = {
      id: root.id,
      parentId: null,
      children: [],
      depth: 0,
      item: null,
      itemIds: [],
      name: root.name,
      path: root.path,
    };
    nodes.set(node.id, node);
    return node;
  });
  for (const item of workspace.items) {
    let parent = nodes.get(item.rootId);
    if (!parent) {
      continue;
    }
    const parts = item.relativePath.split('/');
    if (item.isAvailable) {
      parent.itemIds.push(item.id);
    }
    for (let index = 0; index < parts.length - 1; index += 1) {
      const id = `${item.rootId}/${parts.slice(0, index + 1).join('/')}`;
      let directory = nodes.get(id);
      if (!directory) {
        directory = {
          id,
          parentId: parent.id,
          children: [],
          depth: parent.depth + 1,
          item: null,
          itemIds: [],
          name: parts[index],
          path: parts.slice(0, index + 1).join('/'),
        };
        nodes.set(id, directory);
        parent.children.push(directory);
      }
      if (item.isAvailable) {
        directory.itemIds.push(item.id);
      }
      parent = directory;
    }
    parent.children.push({
      id: item.id,
      parentId: parent.id,
      children: [],
      depth: parent.depth + 1,
      item,
      itemIds: item.isAvailable ? [item.id] : [],
      name: item.name,
      path: item.path,
    });
  }
  roots.forEach(sortChildren);
  return roots;
};

/** Derive a checkbox state from the same eligible leaves for folders and extensions. */
export const selectionState = (
  ids: string[],
  included: ReadonlySet<string>,
): 'mixed' | boolean => {
  const count = ids.filter((id) => included.has(id)).length;
  return count === 0 ? false : count === ids.length ? true : 'mixed';
};

export type VisibleNode = MediaNode & {
  position: number;
  siblingCount: number;
};

/** Flatten only expanded branches so collapsed large folders do not create hidden DOM rows. */
export const visibleTree = (
  nodes: MediaNode[],
  expanded: Readonly<Record<string, boolean>>,
): VisibleNode[] => {
  const rows: VisibleNode[] = [];
  for (const [index, node] of nodes.entries()) {
    rows.push({ ...node, position: index + 1, siblingCount: nodes.length });
    if (!node.item && (expanded[node.id] ?? node.parentId === null)) {
      rows.push(...visibleTree(node.children, expanded));
    }
  }
  return rows;
};
