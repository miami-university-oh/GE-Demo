import * as React from "react";

const MOBILE_BREAKPOINT = 768;

/**
 * Returns `true` when the viewport width is less than 768 px.
 *
 * Subscribes to a `matchMedia` listener so the value updates reactively whenever
 * the viewport crosses the breakpoint — no polling required.
 *
 * @returns `true` if the current viewport is mobile-sized, `false` otherwise.
 */
export function useIsMobile() {
  const [isMobile, setIsMobile] = React.useState<boolean | undefined>(
    undefined
  );

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`);
    const onChange = () => {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    };
    mql.addEventListener("change", onChange);
    setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  return !!isMobile;
}
