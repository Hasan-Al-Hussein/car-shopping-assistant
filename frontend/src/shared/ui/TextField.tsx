import { useId } from "react";
import type { ComponentPropsWithRef } from "react";

type TextFieldProps = Omit<
  ComponentPropsWithRef<"input">,
  "children" | "type" | "aria-invalid" | "aria-errormessage"
> & {
  label: string;
  hint?: string;
  error?: string;
  type?: "text" | "search" | "email" | "tel" | "number" | "date" | "time";
};

export function TextField({
  label,
  hint,
  error,
  id,
  type = "text",
  required = false,
  className = "",
  "aria-describedby": describedBy,
  ...props
}: TextFieldProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const hintId = `${inputId}-hint`;
  const errorId = `${inputId}-error`;
  const descriptionIds = [
    describedBy,
    hint ? hintId : null,
    error ? errorId : null,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="folio-field">
      <label className="folio-field__label" htmlFor={inputId}>
        <bdi dir="auto">{label}</bdi>
        {required ? (
          <>
            {" "}
            <span className="folio-field__requirement">(required)</span>
          </>
        ) : null}
      </label>
      {hint ? (
        <p className="folio-field__hint" id={hintId} dir="auto">
          {hint}
        </p>
      ) : null}
      <input
        {...props}
        id={inputId}
        type={type}
        required={required}
        className={`folio-input ${className}`.trim()}
        aria-invalid={error ? true : undefined}
        aria-describedby={descriptionIds || undefined}
      />
      {error ? (
        <p className="folio-field__error" id={errorId}>
          <span className="folio-field__error-label">Error:</span>{" "}
          <bdi dir="auto">{error}</bdi>
        </p>
      ) : null}
    </div>
  );
}
