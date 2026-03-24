import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { SidebarProvider } from "@/components/layout/sidebar-provider";
import { MobileHeader } from "@/components/layout/mobile-header";
import { SidebarDrawer } from "@/components/layout/sidebar-drawer";
import { CapacitorInit } from "@/components/layout/capacitor-init";
import "@xyflow/react/dist/style.css";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Helaicopter",
  description: "Local viewer for Claude Code conversations, plans, and cost analytics",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <CapacitorInit />
        <TooltipProvider>
          <SidebarProvider>
            <div className="flex min-h-screen">
              {/* Desktop sidebar — hidden on mobile/iPad */}
              <div className="hidden lg:block">
                <AppSidebar />
              </div>

              {/* Mobile/iPad drawer overlay */}
              <SidebarDrawer />

              <div className="flex-1 flex flex-col min-w-0">
                {/* Mobile/iPad header with hamburger */}
                <MobileHeader className="lg:hidden" />

                <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-auto">
                  {children}
                </main>
              </div>
            </div>
          </SidebarProvider>
        </TooltipProvider>
      </body>
    </html>
  );
}
