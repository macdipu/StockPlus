"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { sectionFor, viewFor } from "@/shared/lib/navigation";

/** Section title, its views as tabs, and a one-line description of the view on screen. */
export function SectionHeader() {
  const pathname = usePathname();
  const section = sectionFor(pathname);
  if (!section) return null;
  const view = viewFor(section, pathname);
  return (
    <header className="sectionhead">
      <div className="row" style={{ marginBottom: 6 }}>
        <h1>{section.label}</h1>
        {section.views.length ? (
          <nav className="seg" aria-label={`${section.label} views`}>
            {section.views.map((v) => (
              <Link key={v.key} href={v.href} title={v.description} aria-current={v === view ? "page" : undefined} className={v === view ? "on" : ""}>
                {v.label}
              </Link>
            ))}
          </nav>
        ) : null}
      </div>
      <p className="small mute">{view?.description ?? section.description}</p>
    </header>
  );
}
