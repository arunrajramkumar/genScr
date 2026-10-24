"use client";

import { useEffect, useRef, useState } from "react";

/** True once the element has come within `margin` of the viewport (stays true). Used to lazy-load sections. */
export function useInView<T extends Element>(margin = "300px") {
  const ref = useRef<T>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    if (inView || !ref.current) return;
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const obs = new IntersectionObserver(([e]) => e.isIntersecting && setInView(true), { rootMargin: margin });
    obs.observe(ref.current);
    return () => obs.disconnect();
  }, [inView, margin]);
  return { ref, inView };
}
