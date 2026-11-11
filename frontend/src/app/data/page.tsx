import type { Metadata } from "next";
import { Suspense } from "react";
import { DataPage } from "@/features/data";

export const metadata: Metadata = { title: "Data" };

export default function Page() {
  return (
    <Suspense>
      <DataPage />
    </Suspense>
  );
}
