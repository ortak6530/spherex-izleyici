import { lazy, Suspense, useEffect, useState } from "react";

import AttributionsDialog from "./components/AttributionsDialog";
import Footer from "./components/Footer";
import Hero from "./components/Hero";
import PrivacyNotice from "./components/PrivacyNotice";
import TopBar from "./components/TopBar";
import InfoPanel from "./features/InfoPanel";
import Workspace from "./features/Workspace";
import type { Target } from "./lib/api";
import { track } from "./lib/events";
import { realtime } from "./lib/realtime";

// three.js is ~500 kB; load it after the UI so text appears immediately
const GalaxyBackground = lazy(() => import("./galaxy/GalaxyBackground"));

export default function App() {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [privacyOpen, setPrivacyOpen] = useState(false);
  const [target, setTarget] = useState<Target | null>(null);

  useEffect(() => {
    realtime.start();
    track("page_view");
  }, []);

  return (
    <div className="flex min-h-full flex-col">
      <Suspense fallback={null}>
        <GalaxyBackground />
      </Suspense>
      <TopBar onTarget={setTarget} />
      {target ? (
        <main className="grid flex-1 gap-4 px-3 py-6 sm:px-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
          <Workspace key={target.key} target={target} />
          <div className="space-y-4">
            <InfoPanel key={target.key} target={target} />
          </div>
        </main>
      ) : (
        <main className="flex flex-1 items-center justify-center px-3 py-8 sm:px-6 lg:justify-start lg:px-12">
          <Hero />
        </main>
      )}
      <Footer onSources={() => setSourcesOpen(true)} onPrivacy={() => setPrivacyOpen(true)} />
      <AttributionsDialog open={sourcesOpen} onClose={() => setSourcesOpen(false)} />
      <PrivacyNotice forceOpen={privacyOpen} onClose={() => setPrivacyOpen(false)} />
    </div>
  );
}
