import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Global Radar｜全球金融分析平台",
  description: "私人全球市場研究、投資組合與模擬交易工作台。",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "Global Radar" },
  formatDetection: { telephone: false }
};
export const viewport: Viewport = {
  themeColor: "#08111d",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-Hant"><body>{children}</body></html>;
}