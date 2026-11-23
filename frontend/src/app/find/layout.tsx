import type { ReactNode } from "react";
import { FindFreshness } from "./FindFreshness";
import { SectionHeader } from "@/shared/ui/SectionHeader";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <>
      <SectionHeader />
      <FindFreshness />
      {children}
    </>
  );
}
