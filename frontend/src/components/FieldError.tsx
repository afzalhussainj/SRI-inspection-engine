import type { ReactNode } from "react";

export function FieldError({ id, children }: { id?: string; children: ReactNode }) {
  if (children == null || children === false) return null;
  return (
    <p id={id} className="fieldError" role="alert">
      {children}
    </p>
  );
}
