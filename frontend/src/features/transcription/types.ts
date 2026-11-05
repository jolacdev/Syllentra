import type { WorkspaceDelta } from 'types/pywebview/pywebview-api';

export type Workspace = Omit<WorkspaceDelta, 'reset'>;
export type ConflictChoice = 'overwrite' | 'rename' | 'skip';
