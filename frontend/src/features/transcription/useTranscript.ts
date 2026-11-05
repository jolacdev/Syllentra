import { useEffect, useState } from 'react';

import type { MediaItem, TranscriptPage } from 'types/pywebview/pywebview-api';

/** Fetch only the inspected immutable result and reject responses from an old item or page. */
export const useTranscript = (item: MediaItem | null) => {
  const [cursor, setCursor] = useState({ id: '', offset: 0 });
  const [page, setPage] = useState<null | TranscriptPage>(null);
  const [text, setText] = useState({ id: '', value: '' });
  const [error, setError] = useState<null | { id: string; value: string }>(
    null,
  );
  const resultId = item?.resultId;
  const itemId = item?.id;
  const offset = cursor.id === resultId ? cursor.offset : 0;

  useEffect(() => {
    if (!resultId || !itemId) {
      return;
    }
    let isMounted = true;
    window.pywebview.api
      .get_transcript(itemId, offset)
      .then((next) => {
        if (isMounted) {
          setPage(next);
          setError(null);
          if (offset === 0) {
            setText({ id: next.id, value: next.text });
          }
        }
      })
      .catch((reason: unknown) => {
        if (isMounted) {
          setError({
            id: resultId,
            value: reason instanceof Error ? reason.message : String(reason),
          });
        }
      });
    return () => {
      isMounted = false;
    };
  }, [itemId, offset, resultId]);

  /** Change the preview page while keeping backend content immutable. */
  const navigate = (next: number) =>
    setCursor({ id: resultId ?? '', offset: next });

  return {
    error: error && error.id === resultId ? error.value : null,
    navigate,
    offset,
    page: page && page.id === resultId && page.offset === offset ? page : null,
    text: text.id === resultId ? text.value : '',
  };
};
