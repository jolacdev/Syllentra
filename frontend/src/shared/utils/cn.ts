import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/** Merge conditional classes and resolve Tailwind overrides consistently. */
export const cn = (...classes: ClassValue[]) => twMerge(clsx(...classes));
