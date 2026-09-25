import type { ReactNode } from "react";
import { CinemaIcon } from "../CinemaIcon";

/** A bounded product state; its caller owns all permissions and safe actions. */
export function TaskState({
  eyebrow,
  title,
  children,
  actions,
  tone = "neutral",
  busy = false,
}: {
  eyebrow?: string;
  title: string;
  children: ReactNode;
  actions?: ReactNode;
  tone?: "neutral" | "warning" | "success";
  busy?: boolean;
}) {
  return (
    <div
      className={`inner-task-state inner-task-state--${tone}`}
      role={busy ? "status" : undefined}
    >
      <span className="inner-state-mark" aria-hidden="true">
        <CinemaIcon kind={tone === "success" ? "source" : "compare"} />
      </span>
      <div>
        {eyebrow && <p className="inner-eyebrow">{eyebrow}</p>}
        <h2>{title}</h2>
        <div className="inner-state-copy">{children}</div>
        {actions && <div className="inner-state-actions">{actions}</div>}
      </div>
    </div>
  );
}

export function TaskSupport({
  title,
  status,
  children,
}: {
  title: string;
  status: string;
  children: ReactNode;
}) {
  return (
    <aside className="inner-task-support">
      <div className="inner-support-heading">
        <span className="inner-support-mark">
          <CinemaIcon kind="spark" />
        </span>
        <div>
          <h2>{title}</h2>
          <p>{status}</p>
        </div>
      </div>
      {children}
    </aside>
  );
}
