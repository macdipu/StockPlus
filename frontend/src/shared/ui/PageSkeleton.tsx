/** A grey outline of a page, shown the instant a page change starts so the screen never looks frozen. */
export function PageSkeleton({ what = "Loading page" }: { what?: string }) {
  return (
    <div role="status" aria-live="polite" aria-label={what}>
      <span className="sr-only">{what}…</span>
      <div className="card" aria-hidden="true">
        <div className="skeleton" style={{ height: 22, width: "40%" }} />
        <div className="skeleton" style={{ height: 44, width: "28%", marginTop: 14 }} />
        <div className="skeleton" style={{ height: 14, width: "70%", marginTop: 14 }} />
      </div>
      <div className="skeleton-tabs" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton" style={{ height: 26, width: 90 }} />)}
      </div>
      {[0, 1, 2].map((i) => (
        <div key={i} className="card" aria-hidden="true">
          <div className="skeleton" style={{ height: 16, width: "30%" }} />
          <div className="skeleton" style={{ height: 12, width: "90%", marginTop: 14 }} />
          <div className="skeleton" style={{ height: 12, width: "80%", marginTop: 8 }} />
          <div className="skeleton" style={{ height: 12, width: "60%", marginTop: 8 }} />
        </div>
      ))}
    </div>
  );
}
