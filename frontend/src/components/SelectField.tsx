import type { SelectHTMLAttributes } from "react";
import { FieldError } from "./FieldError";

export function SelectField({
  id,
  label,
  required,
  helpText,
  errorId,
  error,
  placeholder,
  children,
  ...selectProps
}: SelectHTMLAttributes<HTMLSelectElement> & {
  id: string;
  label: string;
  required?: boolean;
  helpText?: string;
  errorId?: string;
  error?: string | null;
  /** Disabled first option label (value must be ""). */
  placeholder: string;
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
      <select
        id={id}
        className={`selectControl${invalid ? " selectControlInvalid" : ""}`}
        aria-invalid={invalid}
        aria-required={required || undefined}
        aria-describedby={described}
        {...selectProps}
      >
        <option value="" disabled>
          {placeholder}
        </option>
        {children}
      </select>
      <FieldError id={errorId}>{error}</FieldError>
    </div>
  );
}
