import type { ReactNode } from "react";
import { SectionHeader } from "@/shared/ui/SectionHeader";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <>
      <SectionHeader />
      {children}
    </>
  );
}
