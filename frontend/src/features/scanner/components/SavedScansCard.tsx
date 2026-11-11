"use client";

import Link from "next/link";
import { useState } from "react";
import { useAuth } from "@/features/auth";
import { describeError } from "@/shared/api";
import { Card } from "@/shared/ui/Card";
import { useSavedScans } from "../hooks/use-scanner-queries";
import type { SavedScan } from "../schemas/scanner";
import type { ScanBody } from "../utils/rules";

interface Props {
  /** The current editor contents as a body, or why it cannot be saved yet. */
  current: { body: ScanBody } | { problem: string };
  onLoad: (scan: SavedScan) => void;
}

export function SavedScansCard({ current, onLoad }: Props) {
  const { state } = useAuth();
  const signedIn = state.status === "authenticated";
  const { list, save, remove } = useSavedScans(signedIn);
  const [name, setName] = useState("");

  if (state.status === "loading") return null;
  if (!signedIn) {
    return (
      <Card title="Saved scans">
        <p className="small mute" style={{ margin: 0 }}>
          <Link href="/login?next=/scanner">Sign in</Link> to save custom scans to your account.
        </p>
      </Card>
    );
  }

  const error = save.error ?? remove.error ?? list.error;
  return (
    <Card title="Saved scans">
      <form
        className="row"
        onSubmit={(e) => {
          e.preventDefault();
          if ("body" in current && name.trim()) save.mutate({ name, body: current.body }, { onSuccess: () => setName("") });
        }}
      >
        <input className="inp" aria-label="Name for this scan" placeholder="Name this scan" value={name} maxLength={60} onChange={(e) => setName(e.target.value)} />
        <button className="btn" type="submit" disabled={!name.trim() || "problem" in current || save.isPending}>Save current</button>
      </form>
      {"problem" in current ? <p className="small mute">{current.problem}</p> : null}
      {error ? <p className="small dn" role="alert">{describeError(error)}</p> : null}
      <ul className="plain" style={{ listStyle: "none", paddingLeft: 0 }}>
        {(list.data ?? []).map((s) => (
          <li key={s.id} className="row" style={{ justifyContent: "space-between" }}>
            <span>{s.name}</span>
            <span>
              <button className="btn ghost small" type="button" onClick={() => onLoad(s)}>Load</button>{" "}
              <button className="btn ghost small" type="button" aria-label={`Delete ${s.name}`} onClick={() => remove.mutate(s.id)}>Delete</button>
            </span>
          </li>
        ))}
        {list.isSuccess && list.data.length === 0 ? <li className="small mute">No saved scans yet.</li> : null}
      </ul>
    </Card>
  );
}
