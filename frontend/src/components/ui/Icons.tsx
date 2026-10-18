// Small stroke icons (24×24 grid, currentColor), so we don't pull in an icon library.

type Props = { className?: string };

function Icon({ d, className = "h-5 w-5" }: { d: string } & Props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <path d={d} />
    </svg>
  );
}

export const HomeIcon = (p: Props) => <Icon {...p} d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" />;
export const CompassIcon = (p: Props) => (
  <Icon {...p} d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zm3.5-12.5-2 5-5 2 2-5z" />
);
export const TrailIcon = (p: Props) => (
  <Icon {...p} d="M5 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm14-10a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM7 17h6a3 3 0 0 0 0-6h-2a3 3 0 0 1 0-6h6" />
);
export const UserIcon = (p: Props) => (
  <Icon {...p} d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-7 9a7 7 0 0 1 14 0" />
);
export const MenuIcon = (p: Props) => <Icon {...p} d="M4 6h16M4 12h16M4 18h16" />;
export const ArrowLeftIcon = (p: Props) => <Icon {...p} d="M19 12H5m6-6-6 6 6 6" />;
export const ExternalIcon = (p: Props) => <Icon {...p} d="M14 4h6v6m0-6-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />;
export const BookmarkIcon = (p: Props) => <Icon {...p} d="M6 3h12v18l-6-4-6 4z" />;
export const CheckIcon = (p: Props) => <Icon {...p} d="m5 12 5 5 9-10" />;
