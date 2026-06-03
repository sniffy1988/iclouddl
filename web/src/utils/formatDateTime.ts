import i18n from "../i18n";
import { normalizeLanguage } from "../i18n/normalizeLanguage";

/** BCP 47 locale for Intl (app `ua` → `uk`). */
function intlLocale(): string {
  const lang = normalizeLanguage(i18n.language);
  return lang === "ua" ? "uk" : lang;
}

/** Browser IANA timezone (e.g. Europe/Kyiv). */
export function userTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

/** Parse API timestamps; naive values are treated as UTC. */
export function parseApiDateTime(value: string): Date {
  const trimmed = value.trim();
  if (/[zZ]$|[+-]\d{2}(:?\d{2})?$/.test(trimmed)) {
    return new Date(trimmed);
  }
  return new Date(`${trimmed}Z`);
}

/** Format an API timestamp in the admin's local timezone and UI locale. */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "";
  const date = parseApiDateTime(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(intlLocale(), {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: userTimeZone(),
  }).format(date);
}
