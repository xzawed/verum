import { useEffect, useRef, useState } from "react";

/**
 * Animates a numeric value from its previous value to `target` over `duration` ms.
 * SSR-safe: starts at 0, animates only on client after mount.
 * Cancels in-flight animation when target changes.
 *
 * @param target The target number to animate to
 * @param duration Animation duration in milliseconds (default: 1200)
 * @returns The currently animated number value
 */
export function useCountUp(target: number, duration = 1200): number {
  const [display, setDisplay] = useState(0);
  const frameRef = useRef<number | null>(null);
  const startRef = useRef<number | null>(null);
  const fromRef = useRef(0);

  useEffect(() => {
    // Cancel any running animation
    if (frameRef.current !== null) {
      cancelAnimationFrame(frameRef.current);
    }
    const from = fromRef.current;
    startRef.current = null;

    const step = (timestamp: number) => {
      if (startRef.current === null) startRef.current = timestamp;
      const elapsed = timestamp - startRef.current;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const value = Math.round(from + (target - from) * eased);
      // eslint-disable-next-line react-compiler/react-compiler -- setState inside rAF callback is intentionally async; not a synchronous render cascade
      setDisplay(value);
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(step);
      } else {
        fromRef.current = target;
        frameRef.current = null;
      }
    };

    frameRef.current = requestAnimationFrame(step);
    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    };
  }, [target, duration]);

  return display;
}
