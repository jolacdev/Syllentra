import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';

import { cn } from '@utils/cn';

type CheckboxProps = {
  checked: 'mixed' | boolean;
  children: ReactNode;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
};

/** Share native checkbox behavior, including mixed-state selection and keyboard access. */
const Checkbox = ({
  checked,
  children,
  disabled = false,
  onChange,
}: CheckboxProps) => {
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (input.current) {
      input.current.indeterminate = checked === 'mixed';
    }
  }, [checked]);
  return (
    <label
      className={cn(
        'flex min-h-9 items-center gap-2.5 text-sm',
        disabled && 'opacity-45',
      )}
    >
      <input
        ref={input}
        checked={checked === true}
        className="accent-accent size-4 shrink-0 rounded"
        disabled={disabled}
        type="checkbox"
        onChange={() => onChange(checked !== true)}
      />
      {children}
    </label>
  );
};

export default Checkbox;
