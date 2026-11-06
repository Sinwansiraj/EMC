import type { Metadata, Viewport } from "next";
import "./globals.css";
import Nav from "./nav";

export const metadata: Metadata = {
  title: "EMC — Error Makes Clever",
  description:
    "EMC (Error Makes Clever) is an AI-assisted career platform that finds roles that fit you, tailors a resume for each, and prepares applications for your review — nothing is sent without your approval.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#0a0e16" },
    { media: "(prefers-color-scheme: light)", color: "#f5f7fb" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Nav />
        <main>{children}</main>
      </body>
    </html>
  );
}
