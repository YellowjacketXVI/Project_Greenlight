import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Morpheus Writ - AI Story Writer",
  description: "AI-powered layered story writing tool",
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
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="min-h-screen antialiased" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}

