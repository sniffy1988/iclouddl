/** Preset sync intervals (seconds). */
export const SYNC_INTERVAL_PRESETS = [
  { label: "Every hour", seconds: 3600 },
  { label: "Every 6 hours", seconds: 21_600 },
  { label: "Every 12 hours", seconds: 43_200 },
  { label: "Daily", seconds: 86_400 },
  { label: "Weekly", seconds: 604_800 },
] as const;

export function secondsToHours(seconds: number): number {
  return Math.round((seconds / 3600) * 100) / 100;
}

export function hoursToSeconds(hours: number): number {
  return Math.max(300, Math.round(hours * 3600));
}

export function formatSyncInterval(seconds: number): string {
  const preset = SYNC_INTERVAL_PRESETS.find((p) => p.seconds === seconds);
  if (preset) return preset.label;
  if (seconds % 86_400 === 0) return `Every ${seconds / 86_400} day(s)`;
  if (seconds % 3600 === 0) return `Every ${seconds / 3600} hour(s)`;
  return `Every ${Math.round(seconds / 60)} min`;
}

export function presetForSeconds(seconds: number): string {
  const match = SYNC_INTERVAL_PRESETS.find((p) => p.seconds === seconds);
  return match ? String(match.seconds) : "custom";
}
