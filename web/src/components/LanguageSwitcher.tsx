import { useTranslation } from "react-i18next";
import {
  LANGUAGE_STORAGE_KEY,
  SUPPORTED_LANGUAGES,
  normalizeLanguage,
  type SupportedLanguage,
} from "../i18n";

type Props = { compact?: boolean };

export default function LanguageSwitcher({ compact = false }: Props) {
  const { i18n, t } = useTranslation();
  const current = normalizeLanguage(i18n.language);

  const change = (lng: SupportedLanguage) => {
    void i18n.changeLanguage(lng);
    localStorage.setItem(LANGUAGE_STORAGE_KEY, lng);
  };

  return (
    <div className={compact ? "" : "mt-4 pt-4 border-t border-slate-800"}>
      <label className="block text-xs text-slate-500 mb-1.5">{t("language.label")}</label>
      <select
        value={current}
        onChange={(e) => change(e.target.value as SupportedLanguage)}
        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-sm text-slate-300"
        aria-label={t("language.label")}
      >
        {SUPPORTED_LANGUAGES.map((lng) => (
          <option key={lng} value={lng}>
            {t(`language.${lng}`)}
          </option>
        ))}
      </select>
    </div>
  );
}
