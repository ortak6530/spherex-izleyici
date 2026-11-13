import { lazy, Suspense, useEffect, useState } from "react";

import Footer from "./components/Footer";
import Hero from "./components/Hero";
import PrivacyNotice from "./components/PrivacyNotice";
import type { SearchRequest } from "./components/SearchBox";
import SourcesPage from "./components/SourcesPage";
import TopBar from "./components/TopBar";
import InfoPanel from "./features/InfoPanel";
import Workspace from "./features/Workspace";
import type { Target } from "./lib/api";
import { track } from "./lib/events";
import { realtime } from "./lib/realtime";

// three.js is ~500 kB; load it after the UI so text appears immediately
const GalaxyBackground = lazy(() => import("./galaxy/GalaxyBackground"));
// Admin panel: only admins open it, so it is not part of the main bundle
const AdminPage = lazy(() => import("./features/AdminPage"));

// Linkable full pages: /#kaynaklar (sources) and /#admin (admin panel)
type Page = "sources" | "admin" | null;
const PAGES: Record<string, Page> = { "#kaynaklar": "sources", "#admin": "admin" };
const pageFromHash = (): Page => PAGES[window.location.hash] ?? null;

export default function App() {
  const [page, setPage] = useState<Page>(pageFromHash);
  const [privacyOpen, setPrivacyOpen] = useState(false);
  const [target, setTarget] = useState<Target | null>(null);
  const [searchRequest, setSearchRequest] = useState<SearchRequest>(null);
  const search = (q: string) => setSearchRequest((r) => ({ q, n: (r?.n ?? 0) + 1 }));

  useEffect(() => {
    realtime.start();
    track("page_view");
    const sync = () => setPage(pageFromHash());
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  const openSources = () => {
    window.location.hash = "#kaynaklar"; // linkable; hashchange updates the state
    window.scrollTo({ top: 0 });
    track("page_view", { page: "sources" });
  };
  const closePage = () => {
    const url = new URL(window.location.href);
    url.hash = "";
    window.history.pushState(null, "", url);
    setPage(null);
  };
  const pickTarget = (t: Target) => {
    if (pageFromHash()) closePage();
    setTarget(t);
  };

  return (
    <div className="flex min-h-full flex-col">
      <Suspense fallback={null}>
        <GalaxyBackground />
      </Suspense>
      <TopBar onTarget={pickTarget} searchRequest={searchRequest} target={target} />
      {page === "sources" ? (
        <main className="flex flex-1 justify-center px-3 py-6 sm:px-6">
          <SourcesPage onBack={closePage} />
        </main>
      ) : page === "admin" ? (
        <main className="flex flex-1 justify-center px-3 py-6 sm:px-6">
          <Suspense fallback={null}>
            <AdminPage onBack={closePage} />
          </Suspense>
        </main>
      ) : target ? (
        <main className="grid flex-1 gap-4 px-3 py-6 sm:px-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
          <Workspace key={target.key} target={target} />
          <div className="space-y-4">
            <InfoPanel key={target.key} target={target} />
          </div>
        </main>
      ) : (
        <main className="flex flex-1 items-center justify-center px-3 py-8 sm:px-6 lg:justify-start lg:px-12">
          <Hero onSearch={search} />
        </main>
      )}
      <Footer onSources={openSources} onPrivacy={() => setPrivacyOpen(true)} />
      <PrivacyNotice forceOpen={privacyOpen} onClose={() => setPrivacyOpen(false)} />
    </div>
  );
}
