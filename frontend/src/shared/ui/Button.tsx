import type { ComponentPropsWithRef } from "react";

type ButtonProps = Omit<ComponentPropsWithRef<"button">, "children"> & {
  children: string;
  variant?: "primary" | "secondary" | "quiet";
};

export function Button({
  children,
  variant = "primary",
  type = "button",
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      type={type}
      className={`folio-button folio-button--${variant} ${className}`.trim()}
    >
      {children}
    </button>
  );
}
