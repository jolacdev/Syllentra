import { useEffect, useRef, useState } from 'react';
import type { DragEvent } from 'react';

/** Bind the stable native drop region while keeping the OS pickers as an explicit fallback. */
export const useNativeDrop = (isDisabled: boolean, isReady: boolean) => {
  const [isAvailable, setIsAvailable] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const depth = useRef(0);
  useEffect(() => {
    if (!isReady) {
      return;
    }
    let isMounted = true;
    window.pywebview.api
      .bind_dropzone()
      .then((available) => {
        if (isMounted) {
          setIsAvailable(available);
        }
      })
      .catch(() => {
        if (isMounted) {
          setIsAvailable(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, [isReady]);

  /** Count nested drag entries without flickering when the pointer crosses child elements. */
  const onDragEnter = (event: DragEvent<HTMLElement>) => {
    if (
      isAvailable &&
      !isDisabled &&
      event.dataTransfer.types.includes('Files')
    ) {
      depth.current += 1;
      setIsDragging(true);
    }
  };
  /** Remove only the current nested drag entry and clear the highlight at the boundary. */
  const onDragLeave = () => {
    depth.current = Math.max(0, depth.current - 1);
    if (depth.current === 0) {
      setIsDragging(false);
    }
  };
  /** Prevent dropped files from navigating away while backend admission remains authoritative. */
  const onDragOver = (event: DragEvent<HTMLElement>) => {
    if (event.dataTransfer.types.includes('Files')) {
      event.preventDefault();
    }
  };
  /** Reset presentation state while Python receives and validates full native paths. */
  const onDropCapture = (event: DragEvent<HTMLElement>) => {
    if (event.dataTransfer.types.includes('Files')) {
      event.preventDefault();
    }
    depth.current = 0;
    setIsDragging(false);
  };
  return {
    onDragEnter,
    onDragLeave,
    onDragOver,
    onDropCapture,
    isAvailable,
    isDragging,
  };
};
