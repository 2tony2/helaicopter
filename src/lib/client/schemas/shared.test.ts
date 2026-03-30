import test from "node:test";
import assert from "node:assert/strict";

import {
  conversationDetailTabSchema,
  isoDateString,
  nonEmptyTrimmedString,
  optionalTrimmedString,
  providerFilterSchema,
  providerSchema,
  urlString,
} from "./shared.ts";

test("nonEmptyTrimmedString trims surrounding whitespace", () => {
  assert.equal(nonEmptyTrimmedString.parse("  hello world  "), "hello world");
});

test("nonEmptyTrimmedString rejects empty strings after trimming", () => {
  assert.throws(() => nonEmptyTrimmedString.parse("   "));
});

test("optionalTrimmedString normalizes blank strings to undefined", () => {
  assert.equal(optionalTrimmedString.parse("   "), undefined);
  assert.equal(optionalTrimmedString.parse(undefined), undefined);
  assert.equal(optionalTrimmedString.parse(null), undefined);
  assert.equal(optionalTrimmedString.parse("  note  "), "note");
});

test("isoDateString accepts ISO-8601 timestamps and rejects invalid dates", () => {
  assert.equal(isoDateString.parse("2026-03-18T10:00:00Z"), "2026-03-18T10:00:00Z");
  assert.throws(() => isoDateString.parse("not-a-date"));
  assert.throws(() => isoDateString.parse("2026-02-30T10:00:00Z"));
});

test("urlString trims and validates absolute URLs", () => {
  assert.equal(urlString.parse(" https://example.com/path "), "https://example.com/path");
  assert.throws(() => urlString.parse("example.com/path"));
});

test("shared enum helpers accept only supported frontend literals", () => {
  assert.equal(providerSchema.parse("claude"), "claude");
  assert.equal(providerFilterSchema.parse("all"), "all");
  assert.equal(conversationDetailTabSchema.parse("messages"), "messages");

  assert.throws(() => providerSchema.parse("anthropic"));
  assert.throws(() => providerFilterSchema.parse("openai"));
  assert.throws(() => conversationDetailTabSchema.parse("unknown"));
});
