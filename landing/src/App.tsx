import { LanguageProvider } from "./i18n";
import LanguageSwitcher from "./components/LanguageSwitcher";
import Hero from "./sections/Hero";
import Results from "./sections/Results";
import Features from "./sections/Features";
import Screenshots from "./sections/Screenshots";
import Architecture from "./sections/Architecture";
import Footer from "./sections/Footer";

export default function App() {
  return (
    <LanguageProvider>
      <div className="min-h-screen">
        <LanguageSwitcher />
        <Hero />
        <Results />
        <Features />
        <Screenshots />
        <Architecture />
        <Footer />
      </div>
    </LanguageProvider>
  );
}
