import type { ComponentPropsWithoutRef, ElementType, ReactNode } from 'react';

import { cn } from '@utils/cn';

const tags = {
  body: 'p',
  caption: 'p',
  eyebrow: 'p',
  sectionTitle: 'h2',
  subtitle: 'h3',
  title: 'h1',
} as const;
const styles = {
  body: 'text-sm leading-6 text-ink/70',
  caption: 'text-xs leading-5 text-ink/70',
  eyebrow: 'text-[10px] font-semibold tracking-[0.13em] text-ink/70',
  sectionTitle: 'text-sm font-semibold',
  subtitle: 'font-semibold',
  title: 'text-3xl leading-tight font-semibold tracking-tight',
};
type Variant = keyof typeof tags;
type TypographyProps<V extends Variant, T extends ElementType | undefined> = {
  children: ReactNode;
  variant: V;
  as?: T;
} & Omit<
  ComponentPropsWithoutRef<T extends ElementType ? T : (typeof tags)[V]>,
  'as' | 'children'
>;

/** Share text roles while preserving the correct HTML element and its typed props. */
const Typography = <
  V extends Variant,
  T extends ElementType | undefined = undefined,
>({
  as = undefined,
  children,
  className,
  variant,
  ...props
}: TypographyProps<V, T>) => {
  const Tag = (as ?? tags[variant]) as ElementType;
  return (
    <Tag className={cn(styles[variant], className)} {...props}>
      {children}
    </Tag>
  );
};

export default Typography;
