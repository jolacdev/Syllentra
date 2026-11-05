import { useCallback, useEffect, useRef, useState } from 'react';

import type {
  BatchAppState,
  BatchPlan,
  CommandError,
  CommandReply,
} from 'types/pywebview/pywebview-api';
import type { PyWebViewStateEvent } from 'types/pywebview/pywebview-state';

import type { ConflictChoice, Workspace } from './types';

/** Hydrate backend-owned batch state and merge bounded collection changes without stale responses. */
export const useTranscription = () => {
  const [hydrationAttempt, setHydrationAttempt] = useState(0);
  const [state, setState] = useState<BatchAppState | null>(null);
  const [workspace, setWorkspace] = useState<null | Workspace>(null);
  const workspaceRef = useRef<null | Workspace>(null);
  const [error, setError] = useState<CommandError | null>(null);
  const [pending, setPending] = useState<ReadonlySet<string>>(new Set());
  const pendingRef = useRef(new Set<string>());
  const [plan, setPlan] = useState<BatchPlan | null>(null);

  /** Normalize native rejections without interpreting English error phrases as application state. */
  const reportError = useCallback((reason: unknown) => {
    setError({
      code: 'unexpected',
      details: reason instanceof Error ? reason.message : String(reason),
    });
  }, []);

  /** Retry failed initial reads while keeping the existing collection and event subscription authoritative. */
  const retryHydration = useCallback(() => {
    setError(null);
    setHydrationAttempt((previous) => previous + 1);
  }, []);

  useEffect(() => {
    let isMounted = true;
    /** Accept only newer state after subscribing before the initial hydration request. */
    const accept = (next: BatchAppState) => {
      if (isMounted) {
        setState((previous) =>
          !previous || next.revision > previous.revision ? next : previous,
        );
      }
    };
    /** Read only the shared property that belongs to the generated application contract. */
    const change = (event: PyWebViewStateEvent) => {
      if (event.detail.key === 'app') {
        accept(event.detail.value);
      }
    };
    window.pywebview.state.addEventListener('change', change);
    window.pywebview.api.get_state().then(accept).catch(reportError);
    return () => {
      isMounted = false;
      window.pywebview.state.removeEventListener('change', change);
    };
  }, [hydrationAttempt, reportError]);

  const collectionRevision = state?.collectionRevision;
  useEffect(() => {
    if (collectionRevision === undefined) {
      return;
    }
    let isMounted = true;
    window.pywebview.api
      .get_workspace(workspaceRef.current?.revision ?? -1)
      .then((delta) => {
        if (
          !isMounted ||
          (workspaceRef.current &&
            delta.revision <= workspaceRef.current.revision)
        ) {
          return;
        }
        const previous = workspaceRef.current;
        const items = new Map(previous?.items.map((item) => [item.id, item]));
        delta.items.forEach((item) => items.set(item.id, item));
        const next: Workspace =
          delta.reset || !previous
            ? {
                items: delta.items,
                revision: delta.revision,
                roots: delta.roots,
              }
            : {
                items: [...items.values()],
                revision: delta.revision,
                roots: previous.roots,
              };
        workspaceRef.current = next;
        setWorkspace(next);
      })
      .catch(reportError);
    return () => {
      isMounted = false;
    };
  }, [collectionRevision, hydrationAttempt, reportError]);

  /** Track distinct pending commands so one response cannot re-enable another in-flight action. */
  const request = useCallback(
    async <T>(key: string, operation: () => Promise<T>): Promise<null | T> => {
      if (pendingRef.current.has(key)) {
        return null;
      }
      pendingRef.current.add(key);
      setPending(new Set(pendingRef.current));
      setError(null);
      try {
        return await operation();
      } catch (reason) {
        reportError(reason);
        return null;
      } finally {
        pendingRef.current.delete(key);
        setPending(new Set(pendingRef.current));
      }
    },
    [reportError],
  );

  /** Launch a typed command with one visible boundary for both returned errors and rejected promises. */
  const act = useCallback(
    (key: string, operation: () => Promise<CommandReply>) => {
      request(key, operation)
        .then((reply) => {
          if (reply?.error) {
            setError(reply.error);
          }
        })
        .catch(reportError);
    },
    [request, reportError],
  );

  /** Review concrete output conflicts or admit a conflict-free plan without a redundant dialog. */
  const prepare = useCallback(
    (failedOnly = false) => {
      request('plan', () => window.pywebview.api.prepare_batch(failedOnly))
        .then((reply) => {
          if (reply?.error) {
            setError(reply.error);
          } else if (reply?.plan) {
            const prepared = reply.plan;
            if (
              prepared.items.some((item) =>
                item.outputs.some((output) => output.action === 'ask'),
              )
            ) {
              setPlan(prepared);
            } else {
              act('start', () => window.pywebview.api.start_batch(prepared.id));
            }
          }
        })
        .catch(reportError);
    },
    [request, act, reportError],
  );

  /** Resolve explicit decisions before submitting the same backend-owned plan identifier. */
  const confirmPlan = useCallback(
    (choices: Readonly<Record<string, ConflictChoice>>) => {
      if (!plan) {
        return;
      }
      request('start', async () => {
        let current = plan;
        const order: ConflictChoice[] = ['skip', 'overwrite', 'rename'];
        for (const action of order) {
          const ids = Object.entries(choices)
            .filter((entry) => entry[1] === action)
            .map((entry) => entry[0]);
          if (!ids.length) {
            continue;
          }
          const reply = await window.pywebview.api.resolve_conflicts(
            current.id,
            ids,
            action,
          );
          if (reply.error) {
            setError(reply.error);
            return;
          }
          if (!reply.plan) {
            throw new Error('The backend returned no output plan.');
          }
          current = reply.plan;
        }
        const reply = await window.pywebview.api.start_batch(current.id);
        if (reply.error) {
          setError(reply.error);
        } else {
          setPlan(null);
        }
      }).catch(reportError);
    },
    [plan, request, reportError],
  );

  return {
    act,
    confirmPlan,
    error,
    pending,
    plan,
    prepare,
    reportError,
    retryHydration,
    setError,
    setPlan,
    state,
    workspace,
  };
};
