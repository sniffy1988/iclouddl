import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";
import de from "./locales/de.json";
import en from "./locales/en.json";
import ru from "./locales/ru.json";
import ua from "./locales/ua.json";
import { normalizeLanguage } from "./normalizeLanguage";

export { LANGUAGE_STORAGE_KEY, SUPPORTED_LANGUAGES, type SupportedLanguage } from "./languages";
export { normalizeLanguage };

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      de: { translation: de },
      ru: { translation: ru },
      ua: { translation: ua },
      uk: { translation: ua },
    },
    fallbackLng: "en",
    supportedLngs: ["en", "de", "ru", "ua", "uk"],
    nonExplicitSupportedLngs: true,
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
      lookupLocalStorage: "iclouddl-lang",
      convertDetectedLanguage: (lng) => normalizeLanguage(lng),
    },
    interpolation: { escapeValue: false },
  });

void i18n.on("initialized", () => {
  const normalized = normalizeLanguage(i18n.language);
  if (normalized !== i18n.language) {
    void i18n.changeLanguage(normalized);
  }
});

export default i18n;
