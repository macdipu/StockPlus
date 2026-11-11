import Link from "next/link";

export default function NotFound() {
  return (
    <div className="card notice">
      <h3>Page not found</h3>
      <p>
        <Link href="/">Go to the dashboard</Link>
      </p>
    </div>
  );
}
