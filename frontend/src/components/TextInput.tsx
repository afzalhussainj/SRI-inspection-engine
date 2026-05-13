import type { InputHTMLAttributes } from "react";
import { FieldError } from "./FieldError";

export function TextInput({
  id,
  label,
  required,
  helpText,
  errorId,
  error,
  ...inputProps
}: InputHTMLAttributes<HTMLInputElement> & {
  id: string;
  label: string;
  required?: boolean;
  helpText?: string;
  errorId?: string;
  error?: string | null;
}) {
  const helpId = helpText ? `${id}_help` : undefined;
  const described = [error ? errorId : undefined, helpId].filter(Boolean).join(" ") || undefined;
  const invalid = Boolean(error);

  return (
    <div className="field">
      <label htmlFor={id} className="fieldLabel">
        {label}
        {required ? (
          <span className="req" aria-hidden>
            *
          </span>
        ) : null}
      </label>
      {helpText ? (
        <div id={helpId} className="muted small fieldHelp">
          {helpText}
        </div>
      ) : null}
      <input
        id={id}
        className={`textControl${invalid ? " textControlInvalid" : ""}`}
        aria-invalid={invalid}
        aria-required={required || undefined}
        aria-describedby={described}
        {...inputProps}
      />
      <FieldError id={errorId}>{error}</FieldError>
    </div>
  );
}
