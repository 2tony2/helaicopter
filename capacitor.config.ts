import type { CapacitorConfig } from "@capacitor/cli";

const serverUrl =
  process.env.HELA_MOBILE_SERVER_URL?.trim() || "http://YOUR_TAILSCALE_HOSTNAME:3000";

const config: CapacitorConfig = {
  appId: "com.helaicopter.app",
  appName: "Helaicopter",
  server: {
    // Point at your Mac's Next.js server over Tailscale or your local network.
    // Export HELA_MOBILE_SERVER_URL before running mobile:ios:* commands.
    url: serverUrl,
    cleartext: serverUrl.startsWith("http://"),
  },
  ios: {
    contentInset: "automatic",
  },
  plugins: {
    SplashScreen: {
      launchAutoHide: true,
      launchShowDuration: 1000,
      backgroundColor: "#0a0a0a",
    },
    StatusBar: {
      style: "DARK",
    },
  },
};

export default config;
