export const SUPPORTED_LANGUAGES = ["en", "de", "ru", "ua"] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

export const LANGUAGE_STORAGE_KEY = "iclouddl-lang";
