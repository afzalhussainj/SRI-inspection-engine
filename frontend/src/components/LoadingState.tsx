import type { ReactNode } from "react";

export function LoadingState({ label, children }: { label: string; children?: ReactNode }) {
  return (
    <div className="loadingState" role="status" aria-live="polite" aria-busy="true">
      <span className="loadingSpinner" aria-hidden />
      <span className="loadingLabel">{label}</span>
      {children}
    </div>
  );
}
