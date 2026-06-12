import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sales AI Assistant",
  description: "Multi-Agent AI Assistant for Sales Teams",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}