import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/hooks/useAuth";
import { OnboardingModal } from "@/components/modals/OnboardingModal";

export const metadata: Metadata = {
  title: "NEXORA AI – Advanced Autonomous Intelligence",
  description: "Production-grade ChatGPT-style neural AI platform with deep reasoning, streaming synthesis, and multi-model orchestration.",
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-slate-50 dark:bg-[#080c14] text-slate-900 dark:text-slate-100 min-h-screen antialiased selection:bg-cyan-500/30 selection:text-cyan-300">
        <AuthProvider>
          {children}
          <OnboardingModal />
        </AuthProvider>
      </body>
    </html>
  );
}

