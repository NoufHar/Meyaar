import type { Metadata } from "next";
import "./globals.css";
import "leaflet/dist/leaflet.css";
import { LanguageProvider } from "@/components/LanguageProvider";

export const metadata: Metadata = {
  title: "Meyaar | Geospatial Validation",
  description:
    "Geospatial data validation and error analysis dashboard.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col"><LanguageProvider>{children}</LanguageProvider></body>
    </html>
  );
}
