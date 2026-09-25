import type { ReactNode } from "react";

type StatusNoticeProps = {
  title: string;
  children?: ReactNode;
  tone?: "neutral" | "success" | "attention" | "error";
  announcement?: "off" | "polite" | "assertive";
  className?: string;
};

/** Choose announcements at the event boundary, not on every status read. */
export function StatusNotice({
  title,
  children,
  tone = "neutral",
  announcement = "off",
  className = "",
}: StatusNoticeProps) {
  const role =
    announcement === "polite"
      ? "status"
      : announcement === "assertive"
        ? "alert"
        : undefined;

  return (
    <div
      className={`folio-notice folio-notice--${tone} ${className}`.trim()}
      role={role}
      aria-atomic={role ? true : undefined}
    >
      <p className="folio-notice__title">
        <strong>{title}</strong>
      </p>
      {children != null ? (
        <div className="folio-notice__body">{children}</div>
      ) : null}
    </div>
  );
}
