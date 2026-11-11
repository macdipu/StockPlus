"use client";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="card notice error" role="alert">
      <h3>Something went wrong</h3>
      <p>{error.message}</p>
      <button className="btn" type="button" onClick={reset}>Try again</button>
    </div>
  );
}
