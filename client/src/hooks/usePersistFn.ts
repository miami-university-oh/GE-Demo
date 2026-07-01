import { useRef } from "react";

type noop = (...args: any[]) => any;

/**
 * Returns a stable function reference that always delegates to the latest `fn` closure.
 *
 * Unlike `useCallback`, the returned reference never changes between renders, so it is
 * safe to pass to child components or effect dependency arrays without causing unnecessary
 * re-renders. Prefer this over `useCallback` for event handlers whose identity should not
 * affect rendering.
 *
 * @param fn - The function to stabilise. Updated on every render via a ref.
 * @returns A permanent wrapper function that forwards all calls to the current `fn`.
 */
export function usePersistFn<T extends noop>(fn: T) {
  const fnRef = useRef<T>(fn);
  fnRef.current = fn;

  const persistFn = useRef<T>(null);
  if (!persistFn.current) {
    persistFn.current = function (this: unknown, ...args) {
      return fnRef.current!.apply(this, args);
    } as T;
  }

  return persistFn.current!;
}
