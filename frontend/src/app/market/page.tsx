import { redirect } from "next/navigation";

/** The market overview is the dashboard at "/"; this path stays as an alias for old links. */
export default function Page() {
  redirect("/");
}
