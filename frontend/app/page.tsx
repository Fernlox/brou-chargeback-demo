import AppShell from "@/components/AppShell";
import { LanguageProvider } from "@/lib/i18n";

export default function Home() {
  return (
    <LanguageProvider>
      <AppShell />
    </LanguageProvider>
  );
}
