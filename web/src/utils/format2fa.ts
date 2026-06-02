import i18n from "../i18n";

export function format2faDaysLeft(daysUntil2faExpires: number | null): string {
  if (daysUntil2faExpires == null) return i18n.t("common.dash");
  if (daysUntil2faExpires === 0) return i18n.t("format2fa.expired");
  if (daysUntil2faExpires === 1) return i18n.t("format2fa.oneDay");
  return i18n.t("format2fa.daysLeft", { count: daysUntil2faExpires });
}
