import './style.css';

export const metadata = {
  title: 'AI cost starter · Veqen',
  description: 'A Next.js and Vercel AI SDK example with a readable cost receipt for every model response.',
};

export default function Layout({ children }) {
  return <html lang="en"><body>{children}</body></html>;
}
