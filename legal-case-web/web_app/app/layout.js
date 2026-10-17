import "./globals.css";

export const metadata = {
  title: "JUDICIAL2 Prototype",
  description: "Gate 1 事實拆解 / Gate 2 底層事實問句生成",
};

export default function RootLayout({ children }) {
  return (
    <html lang="zh-Hant">
      <body>{children}</body>
    </html>
  );
}
