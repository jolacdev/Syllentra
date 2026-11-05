import type { SelectHTMLAttributes } from 'react';

import { cn } from '@utils/cn';

import Icon from './Icon';

type SelectProps = SelectHTMLAttributes<HTMLSelectElement>;

/** Keep native selection behavior with the same sizing and surfaces as buttons. */
const Select = ({ children, className = '', ...props }: SelectProps) => (
  <div
    className={cn('relative min-w-0 rounded-xl focus-within:z-10', className)}
  >
    <select
      className={cn(
        'border-ink/12 bg-surface text-ink h-10 w-full appearance-none rounded-xl border pr-9 pl-3',
        'hover:border-ink/30 text-sm shadow-xs transition-colors focus-visible:outline-offset-[-2px] disabled:cursor-not-allowed disabled:opacity-45',
      )}
      {...props}
    >
      {children}
    </select>
    <Icon
      className="text-ink/60 pointer-events-none absolute top-3 right-3 size-4"
      name="chevron-down"
    />
  </div>
);

export default Select;
