import type { ButtonHTMLAttributes } from 'react';

import { cn } from '@utils/cn';

import Icon from './Icon';
import type { IconName } from './Icon';

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  icon?: IconName;
  variant?: 'danger' | 'ghost' | 'primary' | 'secondary';
};

/** Provide consistent button states without owning application actions. */
const Button = ({
  children,
  className = '',
  icon = undefined,
  type = 'button',
  variant = 'secondary',
  ...props
}: ButtonProps) => (
  <button
    className={cn(
      'inline-flex min-h-10 items-center justify-center gap-2 rounded-xl px-4 py-2',
      'text-sm font-semibold transition-colors disabled:cursor-not-allowed',
      'disabled:opacity-45',
      variant === 'primary'
        ? 'bg-accent hover:bg-accent/90 text-canvas shadow-sm'
        : variant === 'danger'
          ? 'bg-danger hover:bg-danger/90 text-canvas shadow-sm'
          : variant === 'ghost'
            ? 'text-ink/70 hover:bg-ink/5 hover:text-ink'
            : 'border-ink/12 bg-surface text-ink hover:bg-ink/5 border shadow-xs',
      className,
    )}
    type={type}
    {...props}
  >
    {icon && <Icon className="size-4 shrink-0" name={icon} />}
    {children}
  </button>
);

export default Button;
