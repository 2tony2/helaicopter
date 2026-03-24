import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.helaicopter.app",
  appName: "Helaicopter",
  server: {
    // Point at your Mac's Next.js server over Tailscale.
    // Replace YOUR_TAILSCALE_HOSTNAME with your actual hostname from `tailscale status`.
    url: "http://YOUR_TAILSCALE_HOSTNAME:3000",
    cleartext: true, // Tailscale tunnel is already encrypted
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
