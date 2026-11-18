import type { Metadata } from "next";
import { Suspense } from "react";
import { DataPage } from "@/features/data";

export const metadata: Metadata = {
  title: "All shares table",
  description: "Fundamentals and technical values for every DSE share in one sortable table, with CSV export.",
};

export default function Page() {
  return (
    <Suspense>
      <DataPage />
    </Suspense>
  );
}
