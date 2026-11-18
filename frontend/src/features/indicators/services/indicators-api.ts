import { envelope, request } from "@/shared/api";
import { catalogSchema } from "../schemas/catalog";

export const indicatorsApi = {
  catalog: () => request("/charts/indicators", { schema: envelope(catalogSchema) }),
};
