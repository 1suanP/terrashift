/**
 * TerraShift mark: Earth as a simple circle, crossed by a rising time-series line that
 * leaves the globe and ends in a data point. Earth + change over time + measurement.
 */
interface Props {
  size?: number;
  title?: string;
}

export const BrandMark = ({ size = 22, title }: Props) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    role={title ? 'img' : undefined}
    aria-hidden={title ? undefined : true}
    aria-label={title}
    className="brand-mark"
  >
    <circle cx="11" cy="13" r="8.5" fill="currentColor" fillOpacity="0.12" stroke="currentColor" strokeWidth="1.5" />
    <path d="M4.2 16.6c2.6.2 4.2-1.1 5.6-2.9 1.6-2 3.2-4.4 6.6-5.1 1.6-.3 3-.7 4.2-1.6"
      stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    <circle cx="20.6" cy="7" r="1.9" fill="currentColor" />
  </svg>
);
