// frontend/src/stores/sidebar-store.ts
//
// ════════════════════════════════════════════════════════════════
//   SIDEBAR STORE — global UI state for sidebar
// ════════════════════════════════════════════════════════════════
//
// Phase 5f-2 refinements:
//   - Added `openSections` map: persists which sections are expanded
//     across page reloads (per-user preference)
//   - Added `hoverExpanded`: ephemeral state for "hover to peek" behavior
//     when the sidebar is collapsed. NOT persisted — it's a transient
//     interaction state.

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

interface SidebarState {
  /** Desktop: is the sidebar in narrow (icons-only) mode? Persisted. */
  collapsed: boolean;

  /** Mobile: is the off-canvas drawer currently open? Ephemeral. */
  mobileOpen: boolean;

  /**
   * Desktop hover-expand: when the sidebar is COLLAPSED and the user
   * hovers their mouse over it, we temporarily expand it to full width
   * without changing their `collapsed` preference. This lets users peek
   * at the navigation without "uncollapsing" it permanently.
   *
   * Ephemeral — never persisted. Reset on page reload.
   */
  hoverExpanded: boolean;

  /**
   * Per-section open/closed state, keyed by section label.
   * Persisted so the user's expansion preferences survive reloads.
   *
   * Shape: { 'Accounting': true, 'Sales': false, ... }
   * Missing keys fall back to the section's `defaultOpen` from config.
   */
  openSections: Record<string, boolean>;

  // ── Actions ──
  toggleCollapsed: () => void;
  setMobileOpen: (open: boolean) => void;
  setHoverExpanded: (expanded: boolean) => void;
  toggleSection: (label: string) => void;
  setSectionOpen: (label: string, open: boolean) => void;
}

export const useSidebarStore = create<SidebarState>()(
  persist(
    (set) => ({
      collapsed: false,
      mobileOpen: false,
      hoverExpanded: false,
      openSections: {},

      toggleCollapsed: () =>
        set((state) => ({ collapsed: !state.collapsed })),

      setMobileOpen: (open) => set({ mobileOpen: open }),

      setHoverExpanded: (expanded) => set({ hoverExpanded: expanded }),

      toggleSection: (label) =>
        set((state) => ({
          openSections: {
            ...state.openSections,
            [label]: !state.openSections[label],
          },
        })),

      setSectionOpen: (label, open) =>
        set((state) => ({
          openSections: {
            ...state.openSections,
            [label]: open,
          },
        })),
    }),
    {
      name: 'nidus-sidebar',
      storage: createJSONStorage(() => localStorage),
      // Persist `collapsed` AND `openSections`. Skip ephemeral fields.
      partialize: (state) => ({
        collapsed: state.collapsed,
        openSections: state.openSections,
      }),
    },
  ),
);