import i18n from "../i18n";

/** Preset sync intervals (seconds). */
export const SYNC_INTERVAL_PRESETS = [
  { key: "hourly", seconds: 3600 },
  { key: "every6h", seconds: 21_600 },
  { key: "every12h", seconds: 43_200 },
  { key: "daily", seconds: 86_400 },
  { key: "weekly", seconds: 604_800 },
] as const;

export function secondsToHours(seconds: number): number {
  return Math.round((seconds / 3600) * 100) / 100;
}

export function hoursToSeconds(hours: number): number {
  return Math.max(300, Math.round(hours * 3600));
}

export function formatSyncInterval(seconds: number): string {
  const preset = SYNC_INTERVAL_PRESETS.find((p) => p.seconds === seconds);
  if (preset) return i18n.t(`syncInterval.${preset.key}`);
  if (seconds % 86_400 === 0) {
    return i18n.t("syncInterval.everyDays", { count: seconds / 86_400 });
  }
  if (seconds % 3600 === 0) {
    return i18n.t("syncInterval.everyHours", { count: seconds / 3600 });
  }
  return i18n.t("syncInterval.everyMinutes", { count: Math.round(seconds / 60) });
}

export function presetForSeconds(seconds: number): string {
  const match = SYNC_INTERVAL_PRESETS.find((p) => p.seconds === seconds);
  return match ? String(match.seconds) : "custom";
}

export function syncIntervalPresetLabel(seconds: number): string {
  const preset = SYNC_INTERVAL_PRESETS.find((p) => p.seconds === seconds);
  return preset ? i18n.t(`syncInterval.${preset.key}`) : i18n.t("syncInterval.custom");
}
