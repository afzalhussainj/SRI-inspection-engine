import type { ButtonHTMLAttributes, ReactNode } from "react";

export function Button({
  variant = "primary",
  children,
  className = "",
  type = "button",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
  children: ReactNode;
}) {
  const base =
    variant === "primary" ? "buttonPrimary" : variant === "secondary" ? "buttonSecondary" : "buttonGhost";
  const cls = [base, className].filter(Boolean).join(" ");
  return (
    <button type={type} className={cls} {...rest}>
      {children}
    </button>
  );
}
