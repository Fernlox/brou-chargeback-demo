"use client";

import { useState } from "react";

import AdminPanel from "@/components/AdminPanel";
import BrouLogo from "@/components/BrouLogo";
import ChatWindow from "@/components/ChatWindow";
import { useLang } from "@/lib/i18n";

type ViewMode = "chat" | "admin";

export default function AppShell() {
  const [viewMode, setViewMode] = useState<ViewMode>("chat");
  const { lang, setLang, t } = useLang();

  return (
    <div className="min-h-screen bg-brou-gray">
      <header className="h-16 w-full bg-brou-blue text-white">
        <div
          className={[
            "mx-auto flex h-full w-full items-center justify-between px-6",
            viewMode === "admin" ? "max-w-[96rem]" : "max-w-6xl",
          ].join(" ")}
        >
          <div className="flex items-center">
            <BrouLogo className="h-10 w-auto" />
          </div>

          <div className="flex items-center gap-4">
            <p className="hidden text-sm font-medium text-white/90 sm:block">
              {viewMode === "chat" ? t("appShell.titleChat") : t("appShell.titleAdmin")}
            </p>
            <div className="flex items-center gap-1 rounded-lg border border-white/30 bg-white/10 p-1">
              <span className="px-2 text-[11px] font-semibold text-white/80">
                {t("appShell.languageLabel")}
              </span>
              <button
                type="button"
                onClick={() => setLang("es")}
                className={[
                  "rounded-md px-2 py-1 text-xs font-semibold transition",
                  lang === "es" ? "bg-white text-brou-blue" : "text-white hover:bg-white/15",
                ].join(" ")}
              >
                ES
              </button>
              <button
                type="button"
                onClick={() => setLang("en")}
                className={[
                  "rounded-md px-2 py-1 text-xs font-semibold transition",
                  lang === "en" ? "bg-white text-brou-blue" : "text-white hover:bg-white/15",
                ].join(" ")}
              >
                EN
              </button>
            </div>
            <div className="rounded-lg border border-white/30 bg-white/10 p-1">
              <button
                type="button"
                onClick={() => setViewMode("chat")}
                className={[
                  "rounded-md px-3 py-1 text-xs font-semibold transition sm:text-sm",
                  viewMode === "chat"
                    ? "bg-white text-brou-blue"
                    : "text-white hover:bg-white/15",
                ].join(" ")}
              >
                {t("appShell.tabAssistant")}
              </button>
              <button
                type="button"
                onClick={() => setViewMode("admin")}
                className={[
                  "rounded-md px-3 py-1 text-xs font-semibold transition sm:text-sm",
                  viewMode === "admin"
                    ? "bg-white text-brou-blue"
                    : "text-white hover:bg-white/15",
                ].join(" ")}
              >
                {t("appShell.tabAdmin")}
              </button>
            </div>
          </div>
        </div>
      </header>

      <main
        className={[
          "mx-auto w-full px-6 py-6",
          viewMode === "admin" ? "max-w-[96rem]" : "max-w-6xl",
        ].join(" ")}
      >
        <section className="h-[calc(100vh-64px-40px-48px)] min-h-[460px]">
          {viewMode === "chat" ? <ChatWindow /> : <AdminPanel />}
        </section>
      </main>

      <footer className="fixed bottom-0 left-0 h-10 w-full border-t border-slate-200 bg-white/90 py-2 text-center text-xs text-gray-500 backdrop-blur">
        {t("appShell.footer")}
      </footer>
    </div>
  );
}
