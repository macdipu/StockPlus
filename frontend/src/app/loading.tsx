import { PageSkeleton } from "@/shared/ui/PageSkeleton";

/** Shown while a page is being prepared on the server, so a click always shows something at once. */
export default function Loading() {
  return <PageSkeleton />;
}
