import type { ReactNode } from "react";

export type AlertVariant = "info" | "success" | "danger";

export function Alert({
  variant,
  title,
  children,
  role = "status",
  id
}: {
  variant: AlertVariant;
  title?: string;
  children: ReactNode;
  role?: "status" | "alert";
  id?: string;
}) {
  return (
    <div id={id} className={`alert alert-${variant}`} role={role}>
      {title ? <div className="alertTitle">{title}</div> : null}
      <div className="alertBody">{children}</div>
    </div>
  );
}
