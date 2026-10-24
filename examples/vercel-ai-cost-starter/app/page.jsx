import Workbench from './workbench';

export const dynamic = 'force-dynamic';

export default function Page() {
  const liveEnabled = Boolean(process.env.OPENAI_API_KEY && (process.env.DEMO_ACCESS_TOKEN?.length ?? 0) >= 32);
  return <Workbench liveEnabled={liveEnabled} />;
}
