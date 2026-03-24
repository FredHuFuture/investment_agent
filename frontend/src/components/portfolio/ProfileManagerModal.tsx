import { useState, useEffect, useRef } from "react";
import { Button } from "../ui/Button";
import ConfirmModal from "../ui/ConfirmModal";
import { createProfile, updateProfile, deleteProfile } from "../../api/endpoints";
import type { PortfolioProfile } from "../../api/types";
import { useToast } from "../../contexts/ToastContext";

interface ProfileManagerModalProps {
  open: boolean;
  onClose: () => void;
  profiles: PortfolioProfile[];
  onProfilesChange: () => void;
}

export default function ProfileManagerModal({
  open,
  onClose,
  profiles,
  onProfilesChange,
}: ProfileManagerModalProps) {
  const { toast } = useToast();

  // Create form state
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newCash, setNewCash] = useState("100000");
  const [creating, setCreating] = useState(false);

  // Inline edit state
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [saving, setSaving] = useState(false);

  // Delete confirm state
  const [deleteTarget, setDeleteTarget] = useState<PortfolioProfile | null>(null);
  const [deleting, setDeleting] = useState(false);

  const nameInputRef = useRef<HTMLInputElement>(null);
  const editInputRef = useRef<HTMLInputElement>(null);

  // Escape to close
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !deleteTarget) {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose, deleteTarget]);

  // Focus create name input
  useEffect(() => {
    if (showCreate) {
      nameInputRef.current?.focus();
    }
  }, [showCreate]);

  // Focus edit input
  useEffect(() => {
    if (editingId !== null) {
      editInputRef.current?.focus();
      editInputRef.current?.select();
    }
  }, [editingId]);

  // Reset state on close
  useEffect(() => {
    if (!open) {
      setShowCreate(false);
      setNewName("");
      setNewDescription("");
      setNewCash("100000");
      setEditingId(null);
      setEditName("");
    }
  }, [open]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const trimmedName = newName.trim();
    if (!trimmedName) return;
    setCreating(true);
    try {
      const cashNum = parseFloat(newCash) || 100000;
      await createProfile({
        name: trimmedName,
        description: newDescription.trim() || undefined,
        initial_cash: cashNum,
      });
      toast.success("Profile created", `"${trimmedName}" is ready`);
      setShowCreate(false);
      setNewName("");
      setNewDescription("");
      setNewCash("100000");
      onProfilesChange();
    } catch (err) {
      toast.error("Failed to create profile", err instanceof Error ? err.message : "Unknown error");
    } finally {
      setCreating(false);
    }
  }

  async function handleSaveRename(id: number) {
    const trimmedName = editName.trim();
    if (!trimmedName) {
      setEditingId(null);
      return;
    }
    setSaving(true);
    try {
      await updateProfile(id, { name: trimmedName });
      toast.success("Profile renamed", `Now called "${trimmedName}"`);
      setEditingId(null);
      onProfilesChange();
    } catch (err) {
      toast.error("Failed to rename", err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  }

  async function handleConfirmDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteProfile(deleteTarget.id);
      toast.success("Profile deleted", `"${deleteTarget.name}" removed`);
      setDeleteTarget(null);
      onProfilesChange();
    } catch (err) {
      toast.error("Failed to delete", err instanceof Error ? err.message : "Unknown error");
    } finally {
      setDeleting(false);
    }
  }

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center">
        <div
          className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          onClick={onClose}
        />
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="profile-manager-title"
          className="relative w-full max-w-lg rounded-xl bg-gray-900 border border-gray-700 shadow-2xl overflow-hidden"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
            <h2 id="profile-manager-title" className="text-lg font-semibold text-white">
              Manage Profiles
            </h2>
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-gray-300 transition-colors"
              aria-label="Close"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>

          {/* Profile list */}
          <div className="max-h-80 overflow-y-auto">
            {profiles.length === 0 ? (
              <div className="px-6 py-8 text-center text-gray-500 text-sm">
                No profiles yet. Create one below.
              </div>
            ) : (
              <ul className="divide-y divide-gray-800">
                {profiles.map((profile) => (
                  <li
                    key={profile.id}
                    className="px-6 py-3 flex items-center gap-3"
                  >
                    {editingId === profile.id ? (
                      /* Inline rename */
                      <form
                        className="flex-1 flex items-center gap-2"
                        onSubmit={(e) => {
                          e.preventDefault();
                          handleSaveRename(profile.id);
                        }}
                      >
                        <input
                          ref={editInputRef}
                          type="text"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          className="flex-1 px-2 py-1 rounded bg-gray-800 border border-gray-600 text-sm text-white focus:outline-none focus:border-accent"
                          disabled={saving}
                        />
                        <Button
                          variant="primary"
                          size="sm"
                          type="submit"
                          loading={saving}
                          className="min-h-0 py-1 px-2 text-xs"
                        >
                          Save
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          type="button"
                          onClick={() => setEditingId(null)}
                          disabled={saving}
                          className="min-h-0 py-1 px-2 text-xs"
                        >
                          Cancel
                        </Button>
                      </form>
                    ) : (
                      /* Normal display */
                      <>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-white truncate">
                              {profile.name}
                            </span>
                            {profile.is_default === 1 && (
                              <span className="shrink-0 text-[10px] font-semibold uppercase tracking-wider bg-accent/20 text-accent-light px-1.5 py-0.5 rounded">
                                Active
                              </span>
                            )}
                          </div>
                          {profile.description && (
                            <div className="text-xs text-gray-500 truncate mt-0.5">
                              {profile.description}
                            </div>
                          )}
                        </div>

                        <div className="flex items-center gap-1 shrink-0">
                          {/* Edit/rename button */}
                          <button
                            onClick={() => {
                              setEditingId(profile.id);
                              setEditName(profile.name);
                            }}
                            className="p-1.5 text-gray-500 hover:text-gray-300 transition-colors rounded hover:bg-gray-800"
                            aria-label={`Rename ${profile.name}`}
                            title="Rename"
                          >
                            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                            </svg>
                          </button>
                          {/* Delete button (disabled for default) */}
                          <button
                            onClick={() => setDeleteTarget(profile)}
                            disabled={profile.is_default === 1}
                            className={`
                              p-1.5 rounded transition-colors
                              ${profile.is_default === 1
                                ? "text-gray-700 cursor-not-allowed"
                                : "text-gray-500 hover:text-red-400 hover:bg-gray-800"
                              }
                            `}
                            aria-label={`Delete ${profile.name}`}
                            title={profile.is_default === 1 ? "Cannot delete the active profile" : "Delete"}
                          >
                            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                              <polyline points="3 6 5 6 21 6" />
                              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                            </svg>
                          </button>
                        </div>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Create new profile */}
          <div className="border-t border-gray-800 px-6 py-4">
            {showCreate ? (
              <form onSubmit={handleCreate} className="space-y-3">
                <div>
                  <label htmlFor="profile-name" className="block text-xs font-medium text-gray-400 mb-1">
                    Profile Name *
                  </label>
                  <input
                    ref={nameInputRef}
                    id="profile-name"
                    type="text"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="e.g. Growth Portfolio"
                    className="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-accent"
                    required
                    disabled={creating}
                  />
                </div>
                <div>
                  <label htmlFor="profile-description" className="block text-xs font-medium text-gray-400 mb-1">
                    Description
                  </label>
                  <input
                    id="profile-description"
                    type="text"
                    value={newDescription}
                    onChange={(e) => setNewDescription(e.target.value)}
                    placeholder="Optional description"
                    className="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-accent"
                    disabled={creating}
                  />
                </div>
                <div>
                  <label htmlFor="profile-cash" className="block text-xs font-medium text-gray-400 mb-1">
                    Initial Cash ($)
                  </label>
                  <input
                    id="profile-cash"
                    type="number"
                    min="0"
                    step="1000"
                    value={newCash}
                    onChange={(e) => setNewCash(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-accent"
                    disabled={creating}
                  />
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="primary"
                    size="sm"
                    type="submit"
                    loading={creating}
                    disabled={!newName.trim()}
                  >
                    Create Profile
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    type="button"
                    onClick={() => setShowCreate(false)}
                    disabled={creating}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            ) : (
              <Button
                variant="secondary"
                size="sm"
                className="w-full"
                onClick={() => setShowCreate(true)}
                data-testid="create-profile-btn"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                New Profile
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Delete confirmation */}
      <ConfirmModal
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleConfirmDelete}
        title={`Delete "${deleteTarget?.name}"?`}
        description="This will permanently delete this portfolio profile and all its positions. This action cannot be undone."
        confirmLabel="Delete Profile"
        variant="danger"
        loading={deleting}
      />
    </>
  );
}
