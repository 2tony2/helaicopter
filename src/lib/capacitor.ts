import { Capacitor } from "@capacitor/core";
import { App } from "@capacitor/app";
import { StatusBar, Style } from "@capacitor/status-bar";

/**
 * Initialize Capacitor native features.
 * No-ops gracefully when running in a regular browser.
 */
export async function initCapacitor() {
  if (!Capacitor.isNativePlatform()) return;

  try {
    await StatusBar.setStyle({ style: Style.Dark });
  } catch {
    // StatusBar not available
  }

  App.addListener("appStateChange", ({ isActive }) => {
    if (isActive) {
      window.dispatchEvent(new Event("focus"));
    }
  });
}
