import { useEffect } from "react";

export function usePageTitle(title: string): void {
  useEffect(() => {
    document.title = `${title} | Investment Agent`;
    return () => {
      document.title = "Investment Agent";
    };
  }, [title]);
}
