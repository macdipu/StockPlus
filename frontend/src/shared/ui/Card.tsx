import type { ReactNode } from "react";

interface CardProps {
  title?: ReactNode;
  children: ReactNode;
  className?: string;
  /** Accessible name for the region when there is no visible title. */
  label?: string;
}

export function Card({ title, children, className, label }: CardProps) {
  return (
    <section className={`card ${className ?? ""}`} aria-label={typeof title === "string" ? title : label}>
      {title ? <h3>{title}</h3> : null}
      {children}
    </section>
  );
}
