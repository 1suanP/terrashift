/**
 * One tooltip for the whole app: any element with a `data-tip` attribute gets a
 * tooltip on hover or keyboard focus. Rendered position: fixed, so scrolling panels
 * never clip it.
 */
import { useEffect, useRef, useState } from 'react';

interface Tip {
  text: string;
  x: number;
  y: number;
  below: boolean;
}

export const TooltipLayer = () => {
  const [tip, setTip] = useState<Tip | null>(null);
  const timer = useRef(0);

  useEffect(() => {
    const show = (target: EventTarget | null) => {
      const el = (target as HTMLElement | null)?.closest?.('[data-tip]') as HTMLElement | null;
      window.clearTimeout(timer.current);
      if (!el) { setTip(null); return; }
      const text = el.getAttribute('data-tip') || '';
      if (!text) { setTip(null); return; }
      timer.current = window.setTimeout(() => {
        const r = el.getBoundingClientRect();
        const below = r.top < 90;
        setTip({ text, x: r.left + r.width / 2, y: below ? r.bottom + 8 : r.top - 8, below });
      }, 350);
    };
    const over = (e: Event) => show(e.target);
    const hide = () => { window.clearTimeout(timer.current); setTip(null); };
    document.addEventListener('pointerover', over);
    document.addEventListener('focusin', over);
    document.addEventListener('pointerdown', hide);
    document.addEventListener('scroll', hide, true);
    return () => {
      document.removeEventListener('pointerover', over);
      document.removeEventListener('focusin', over);
      document.removeEventListener('pointerdown', hide);
      document.removeEventListener('scroll', hide, true);
    };
  }, []);

  if (!tip) return null;
  const left = Math.min(window.innerWidth - 150, Math.max(150, tip.x));
  return (
    <div className={`tooltip ${tip.below ? 'below' : ''}`} style={{ left, top: tip.y }} role="tooltip">
      {tip.text}
    </div>
  );
};
