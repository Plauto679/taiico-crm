import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";
import { SessionActivityGuard } from "@/components/auth/SessionActivityGuard";
import { NavigationProgress } from "@/components/navigation/NavigationProgress";

export const metadata: Metadata = {
  metadataBase: new URL("https://taiico-crm.com"),
  title: "TAIICO CRM",
  description: "Sistema de gestión para TAIICO Life Advisors",
  applicationName: "TAIICO CRM",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: [{ url: "/logo.png", type: "image/png", sizes: "512x512" }],
    apple: [{ url: "/logo.png", type: "image/png", sizes: "512x512" }],
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "TAIICO CRM",
  },
  openGraph: {
    type: "website",
    locale: "es_MX",
    url: "/",
    siteName: "TAIICO CRM",
    title: "TAIICO CRM",
    description: "Sistema de gestión para TAIICO Life Advisors",
    images: [
      {
        url: "/logo.png",
        width: 512,
        height: 512,
        alt: "TAIICO Life Advisors",
      },
    ],
  },
  twitter: {
    card: "summary",
    title: "TAIICO CRM",
    description: "Sistema de gestión para TAIICO Life Advisors",
    images: ["/logo.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body>
        <div className="flex h-screen bg-gray-100">
          <SessionActivityGuard />
          <NavigationProgress />
          <Sidebar />
          <main className="min-w-0 flex-1 flex flex-col overflow-hidden bg-[#34587C]">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
