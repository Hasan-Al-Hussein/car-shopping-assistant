export function CinemaIcon({
  kind,
}: {
  kind:
    | "spark"
    | "sparkle"
    | "robot"
    | "search"
    | "compare"
    | "source"
    | "arrow"
    | "settings";
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {kind === "settings" ? (
        <>
          <path d="m9 3-.7 2.1-1.9 1.1-2.2-.4-2 3.4 1.5 1.7v2.2l-1.5 1.7 2 3.4 2.2-.4 1.9 1.1L9 21h4l.7-2.1 1.9-1.1 2.2.4 2-3.4-1.5-1.7v-2.2l1.5-1.7-2-3.4-2.2.4-1.9-1.1L13 3Z" />
          <circle cx="11" cy="12" r="3" />
        </>
      ) : kind === "robot" ? (
        <>
          <rect x="4" y="7" width="16" height="13" rx="5" />
          <path d="M12 7V4M2 12v4m20-4v4M9 16h6" />
          <circle cx="12" cy="3" r="1" />
          <circle cx="8.5" cy="12" r=".8" fill="currentColor" />
          <circle cx="15.5" cy="12" r=".8" fill="currentColor" />
        </>
      ) : kind === "spark" || kind === "sparkle" ? (
        <path d="m12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5Z" />
      ) : kind === "search" ? (
        <>
          <circle cx="10.5" cy="10.5" r="6.5" />
          <path d="m16 16 5 5" />
        </>
      ) : kind === "compare" ? (
        <>
          <path d="M4 6h16M4 18h16M8 3v6m8 6v6" />
          <circle cx="8" cy="6" r="2" />
          <circle cx="16" cy="18" r="2" />
        </>
      ) : kind === "source" ? (
        <>
          <path d="m12 3 8 3v6c0 4-5 8-8 9-3-1-8-5-8-9V6Z" />
          <path d="m8 12 3 3 5-6" />
        </>
      ) : (
        <path d="M4 12h15m-6-6 6 6-6 6" />
      )}
    </svg>
  );
}
