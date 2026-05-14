"use client";

import { useState } from "react";

import AdminPanel from "@/components/AdminPanel";
import BrouLogo from "@/components/BrouLogo";
import ChatWindow from "@/components/ChatWindow";

type ViewMode = "chat" | "admin";

export default function AppShell() {
  const [viewMode, setViewMode] = useState<ViewMode>("chat");

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
              {viewMode === "chat" ? "Asistente de Reclamos" : "Panel de Administracion"}
            </p>
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
                Asistente
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
                Admin
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
        Demo - datos ficticios
      </footer>
    </div>
  );
}
