import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Senior Full-Stack Engineer, AI & Digital Health",
  description:
    "Practice interview for senior full-stack engineer role at Last Mile Health.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
