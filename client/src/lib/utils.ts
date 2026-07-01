import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merges class names using clsx and deduplicates conflicting Tailwind classes via tailwind-merge.
 *
 * @param inputs - One or more class values (strings, arrays, objects, etc.) accepted by clsx.
 * @returns A single deduplicated class string safe to pass to `className`.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
