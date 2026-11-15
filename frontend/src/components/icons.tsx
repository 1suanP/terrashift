/** Small line icons (inline SVG, no icon library). */
import type { ReactElement, SVGProps } from 'react';

const base = (props: SVGProps<SVGSVGElement>) => ({
  width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
  strokeWidth: 1.6, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true, ...props,
});

export const IconDrop = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M12 3c3.5 4.4 6 7.8 6 11a6 6 0 0 1-12 0c0-3.2 2.5-6.6 6-11z" /></svg>
);
export const IconThermo = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0z" /><path d="M12 9v7" /></svg>
);
export const IconSoil = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M3 9h18M3 14h18M3 19h18" /><path d="M12 9V4M9 6l3-2 3 2" /></svg>
);
export const IconVapor = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M3 18c2 0 2-1.5 4-1.5S9 18 11 18s2-1.5 4-1.5 2 1.5 4 1.5" /><path d="M8 13V5M12 13V3M16 13V6" /><path d="M6.5 6.5 8 5l1.5 1.5M10.5 4.5 12 3l1.5 1.5M14.5 7.5 16 6l1.5 1.5" /></svg>
);
export const IconRiver = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M5 3c4 3-2 6 2 9s-2 6 2 9M15 3c4 3-2 6 2 9s-2 6 2 9" /></svg>
);
export const IconGrid = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><rect x="4" y="4" width="6" height="6" rx="1" /><rect x="14" y="4" width="6" height="6" rx="1" /><rect x="4" y="14" width="6" height="6" rx="1" /><rect x="14" y="14" width="6" height="6" rx="1" /></svg>
);
export const IconPlus = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M12 5v14M5 12h14" /></svg>;
export const IconMinus = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M5 12h14" /></svg>;
export const IconReset = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><circle cx="12" cy="12" r="8" /><path d="M4 12h3M17 12h3M12 4v3M12 17v3" /></svg>
);
export const IconBox = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M4 8V4h4M16 4h4v4M20 16v4h-4M8 20H4v-4" /><rect x="8" y="8" width="8" height="8" rx="1" strokeDasharray="2 2" /></svg>
);
export const IconLayers = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="m12 4 9 5-9 5-9-5 9-5z" /><path d="m3 14 9 5 9-5" /></svg>
);
export const IconPlay = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M8 5v14l11-7z" fill="currentColor" /></svg>;
export const IconPause = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M8 5v14M16 5v14" strokeWidth={3} /></svg>
);
export const IconClose = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="M6 6l12 12M18 6 6 18" /></svg>;
export const IconChevron = (p: SVGProps<SVGSVGElement>) => <svg {...base(p)}><path d="m9 6 6 6-6 6" /></svg>;
export const IconPin = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z" /><circle cx="12" cy="9.5" r="2.5" /></svg>
);
export const IconInfo = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7.5v.5" /></svg>
);
export const IconRotate = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M20 12a8 8 0 1 1-2.3-5.6" /><path d="M20 4v4h-4" /></svg>
);
export const IconTrend = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M3 17l6-6 4 4 8-8" /><path d="M15 7h6v6" /></svg>
);

export const VARIABLE_ICONS: Record<string, (p: SVGProps<SVGSVGElement>) => ReactElement> = {
  precipitation: IconDrop,
  temperature: IconThermo,
  soil: IconSoil,
  evaporation: IconVapor,
  streamflow: IconRiver,
  other: IconGrid,
};
