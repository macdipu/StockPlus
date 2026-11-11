import { describeError } from "@/shared/api";

export function Loading({ what = "Loading" }: { what?: string }) {
  return (
    <div className="notice" role="status" aria-live="polite">
      {what}…
    </div>
  );
}

export function ErrorNotice({ error }: { error: unknown }) {
  return (
    <div className="notice error" role="alert">
      {describeError(error)}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="notice">{children}</div>;
}
