import type { Metadata } from "next";
import "./globals.css";
import Nav from "./nav";

export const metadata: Metadata = {
  title: "EMC — Error Makes Clever",
  description: "EMC (Error Makes Clever) is a customised job hunter that finds roles, tailors resumes, and prepares applications for your review.",
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
