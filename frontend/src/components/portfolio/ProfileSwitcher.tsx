import { useState, useEffect, useRef, useCallback } from "react";
import { Button } from "../ui/Button";
import { listProfiles, setDefaultProfile } from "../../api/endpoints";
import type { PortfolioProfile } from "../../api/types";
import { useToast } from "../../contexts/ToastContext";
import ProfileManagerModal from "./ProfileManagerModal";

interface ProfileSwitcherProps {
  /** Called after the active profile is changed so the parent can refetch data */
  onProfileChange: () => void;
}

export default function ProfileSwitcher({ onProfileChange }: ProfileSwitcherProps) {
  const { toast } = useToast();
  const [profiles, setProfiles] = useState<PortfolioProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [switching, setSwitching] = useState<number | null>(null);
  const [managerOpen, setManagerOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const fetchProfiles = useCallback(async () => {
    try {
      const res = await listProfiles();
      setProfiles(res.data);
    } catch {
      // Silently fail on initial load; profiles just won't appear
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProfiles();
  }, [fetchProfiles]);

  // Close dropdown when clicking outside
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  // Close dropdown on Escape
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open]);

  const activeProfile = profiles.find((p) => p.is_default === 1);
  const displayName = activeProfile?.name ?? "Default";

  async function handleSwitch(profile: PortfolioProfile) {
    if (profile.is_default === 1) {
      setOpen(false);
      return;
    }
    setSwitching(profile.id);
    try {
      await setDefaultProfile(profile.id);
      toast.success("Profile switched", `Now using "${profile.name}"`);
      await fetchProfiles();
      setOpen(false);
      onProfileChange();
    } catch (err) {
      toast.error("Failed to switch profile", err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSwitching(null);
    }
  }

  function handleManagerClose() {
    setManagerOpen(false);
    // Refresh profiles after managing (create/rename/delete)
    fetchProfiles();
  }

  if (loading) {
    return (
      <div className="h-[44px] w-36 animate-pulse rounded-lg bg-gray-800" />
    );
  }

  // If there are no profiles at all, don't render
  if (profiles.length === 0) return null;

  return (
    <>
      <div className="relative" ref={dropdownRef}>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setOpen((prev) => !prev)}
          aria-haspopup="listbox"
          aria-expanded={open}
          data-testid="profile-switcher-trigger"
        >
          <svg
            className="w-4 h-4 shrink-0"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
          <span className="truncate max-w-[120px]">{displayName}</span>
          <svg
            className={`w-3 h-3 shrink-0 transition-transform ${open ? "rotate-180" : ""}`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </Button>

        {open && (
          <div
            className="absolute right-0 top-full mt-1 z-40 w-64 rounded-xl bg-gray-900 border border-gray-700 shadow-2xl overflow-hidden"
            role="listbox"
            aria-label="Portfolio profiles"
          >
            <div className="py-1 max-h-60 overflow-y-auto">
              {profiles.map((profile) => (
                <button
                  key={profile.id}
                  role="option"
                  aria-selected={profile.is_default === 1}
                  onClick={() => handleSwitch(profile)}
                  disabled={switching !== null}
                  className={`
                    w-full text-left px-4 py-2.5 flex items-center gap-3
                    transition-colors disabled:opacity-50
                    ${profile.is_default === 1
                      ? "bg-blue-600/10 text-blue-400"
                      : "text-gray-300 hover:bg-gray-800"
                    }
                  `}
                >
                  {/* Radio indicator */}
                  <span
                    className={`
                      w-4 h-4 rounded-full border-2 shrink-0 flex items-center justify-center
                      ${profile.is_default === 1
                        ? "border-blue-500"
                        : "border-gray-600"
                      }
                    `}
                  >
                    {profile.is_default === 1 && (
                      <span className="w-2 h-2 rounded-full bg-blue-500" />
                    )}
                  </span>

                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium truncate">
                      {profile.name}
                      {switching === profile.id && (
                        <span className="ml-2 h-3 w-3 inline-block animate-spin rounded-full border-2 border-current border-t-transparent" />
                      )}
                    </div>
                    {profile.description && (
                      <div className="text-xs text-gray-500 truncate">
                        {profile.description}
                      </div>
                    )}
                  </div>
                </button>
              ))}
            </div>

            <div className="border-t border-gray-700 p-2">
              <Button
                variant="ghost"
                size="sm"
                className="w-full justify-center text-xs"
                onClick={() => {
                  setOpen(false);
                  setManagerOpen(true);
                }}
                data-testid="manage-profiles-btn"
              >
                <svg
                  className="w-3.5 h-3.5"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.32 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
                Manage Profiles
              </Button>
            </div>
          </div>
        )}
      </div>

      <ProfileManagerModal
        open={managerOpen}
        onClose={handleManagerClose}
        profiles={profiles}
        onProfilesChange={fetchProfiles}
      />
    </>
  );
}
