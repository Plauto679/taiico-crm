import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";
import { SessionActivityGuard } from "@/components/auth/SessionActivityGuard";
import { NavigationProgress } from "@/components/navigation/NavigationProgress";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "TAIICO CRM",
  description: "Sistema de gestión para TAIICO Life Advisors",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body className={inter.className}>
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
