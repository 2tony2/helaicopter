import { z } from "zod";

import {
  conversationDetailTabs,
  orchestrationTabs,
} from "../../routes.ts";

function enumSchema<const Values extends readonly [string, ...string[]]>(values: Values) {
  return z.enum(values);
}

const trimmedString = z.string().trim();

export const nonEmptyTrimmedString = trimmedString.min(1, "Expected a non-empty string.");

export const optionalTrimmedString = z.union([
  trimmedString.min(1),
  trimmedString.length(0).transform(() => undefined),
  z.undefined(),
  z.null().transform(() => undefined),
]);

export const isoDateString = trimmedString.refine(
  (value) =>
    z.iso.date().safeParse(value).success || z.iso.datetime({ offset: true }).safeParse(value).success,
  "Expected an ISO 8601 date string."
);

export const urlString = trimmedString.url("Expected an absolute URL.");

export const providers = ["claude", "codex"] as const;
export const providerSchema = enumSchema(providers);

export const providerFilters = ["all", ...providers] as const;
export const providerFilterSchema = enumSchema(providerFilters);

export const conversationDetailTabSchema = enumSchema(conversationDetailTabs);

export const orchestrationTabSchema = enumSchema(orchestrationTabs);
