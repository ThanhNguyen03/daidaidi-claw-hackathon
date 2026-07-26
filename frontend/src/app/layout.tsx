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
  title: 'AdtimaBox Sales Agent',
  description: 'Multi-Agent AI Assistant for Sales Teams',
  icons: {
    icon: '/favicon.svg',
  },
};

// Applied before first paint. React can only add the `dark` class after hydration,
// which is long enough to show a full-brightness white flash on every load — worse
// than no dark mode at all in a dim room.
const THEME_BOOTSTRAP = `
try {
  if (localStorage.getItem('theme') !== 'light') {
    document.documentElement.classList.add('dark');
  }
} catch (e) {
  document.documentElement.classList.add('dark');
}
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={beVietnamPro.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
