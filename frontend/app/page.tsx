import ChatWindow from "@/components/ChatWindow";

export default function Home() {
  return (
    <div className="min-h-screen bg-brou-gray">
      <header className="h-16 w-full bg-brou-blue text-white">
        <div className="mx-auto flex h-full w-full max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-sm bg-white text-xl font-extrabold text-brou-blue">
              B
            </div>
            <span className="text-2xl font-bold tracking-wider">BROU</span>
          </div>
          <p className="text-sm font-medium text-white/90 sm:text-base">
            Asistente de Reclamos
          </p>
        </div>
      </header>

      <main className="mx-auto w-full max-w-3xl px-6 py-6">
        <section className="h-[calc(100vh-64px-40px-48px)] min-h-[460px]">
          <ChatWindow />
        </section>
      </main>

      <footer className="fixed bottom-0 left-0 h-10 w-full border-t border-slate-200 bg-white/90 py-2 text-center text-xs text-gray-500 backdrop-blur">
        Demo - datos ficticios
      </footer>
    </div>
  );
}
