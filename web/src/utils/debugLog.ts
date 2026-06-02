let debugLoggingEnabled = false;

export function setDebugLoggingEnabled(enabled: boolean) {
  debugLoggingEnabled = enabled;
}

export function isDebugLoggingEnabled() {
  return debugLoggingEnabled;
}

export function debugLog(...args: unknown[]) {
  if (debugLoggingEnabled) {
    console.debug("[iCloud DL]", ...args);
  }
}

export function debugInfo(...args: unknown[]) {
  if (debugLoggingEnabled) {
    console.info("[iCloud DL]", ...args);
  }
}

export function debugWarn(...args: unknown[]) {
  if (debugLoggingEnabled) {
    console.warn("[iCloud DL]", ...args);
  }
}
