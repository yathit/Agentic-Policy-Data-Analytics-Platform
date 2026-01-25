import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "IMDA Policy Analytics",
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
