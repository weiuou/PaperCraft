import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI PaperCraft Studio",
  description: "Internal MVP workbench for AI PaperCraft Studio.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
