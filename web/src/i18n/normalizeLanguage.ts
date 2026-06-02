import { SUPPORTED_LANGUAGES, type SupportedLanguage } from "./languages";

/** Map browser / stored codes to supported app locales (e.g. uk → ua). */
export function normalizeLanguage(lng: string): SupportedLanguage {
  const base = lng.split("-")[0].toLowerCase();
  if (base === "uk") return "ua";
  if (SUPPORTED_LANGUAGES.includes(base as SupportedLanguage)) {
    return base as SupportedLanguage;
  }
  return "en";
}
