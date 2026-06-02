export const LOG_LEVELS = ["OFF", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] as const;

export type LogLevel = (typeof LOG_LEVELS)[number];

export function isLoggingActive(level: string | undefined | null): boolean {
  return Boolean(level && level !== "OFF");
}

export function browserConsoleDebugEnabled(level: string | undefined | null): boolean {
  return level === "DEBUG";
}
