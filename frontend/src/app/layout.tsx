import type { Metadata } from 'next';
import { Be_Vietnam_Pro } from 'next/font/google';
import './globals.css';

// Signature font with full Vietnamese support (latin + vietnamese subsets).
// Vietnamese diacritics (ế, ữ, ợ, đ, …) render correctly.
const beVietnamPro = Be_Vietnam_Pro({
  subsets: ['latin', 'vietnamese'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-sans',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Sales AI Assistant',
  description: 'Multi-Agent AI Assistant for Sales Teams',
  icons: {
    icon: '/favicon.svg',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={beVietnamPro.variable}>
      <body>{children}</body>
    </html>
  );
}
