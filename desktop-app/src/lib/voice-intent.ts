/**
 * Interprets a spoken reply to a pending confirmation. Deliberately narrow —
 * this only needs to catch "yes" and "no" in their common spoken forms, not
 * parse arbitrary intent.
 */
export type ConfirmationIntent = "yes" | "no" | null;

const YES_WORDS = [
  "yes",
  "yeah",
  "yep",
  "yup",
  "confirm",
  "confirmed",
  "approve",
  "approved",
  "affirmative",
  "do it",
  "go ahead",
  "proceed",
  "sure",
  "okay",
  "ok",
];

const NO_WORDS = [
  "no",
  "nope",
  "nah",
  "cancel",
  "cancelled",
  "deny",
  "denied",
  "negative",
  "stop",
  "don't",
  "do not",
  "abort",
];

export function parseConfirmationIntent(text: string): ConfirmationIntent {
  const normalized = text.trim().toLowerCase().replace(/[.!?]+$/, "");
  if (!normalized) return null;

  const isWord = (list: string[]) =>
    list.some((word) => normalized === word || normalized.startsWith(`${word} `) || normalized.endsWith(` ${word}`));

  if (isWord(YES_WORDS)) return "yes";
  if (isWord(NO_WORDS)) return "no";
  return null;
}
