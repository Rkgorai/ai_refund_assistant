import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Refund Assistant",
  description: "Next.js UI for LangGraph Refund Agent",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
