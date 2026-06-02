import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

import type { ChorusSegment } from "../api/music";

export type AvatarKind = "preset" | "image" | "video";

export interface SelectedAvatar {
  kind: AvatarKind;
  id: string;
  name: string;
  thumbnailUrl?: string | null;
}

export interface SliceInfo {
  sliceId: string;
  musicId: string;
  start: number;
  end: number;
  downloadUrl: string;
}

export interface CurrentMusic {
  musicId: string;
  filename: string;
  duration: number;
  chorus: ChorusSegment | null;
  peaks: number[];
}

export interface CurrentTask {
  taskId: string;
  status: string;
  progress: number;
  stage: string;
  message?: string | null;
}

interface AppState {
  currentMusic: CurrentMusic | null;
  selectedSegment: { start: number; end: number } | null;
  slice: SliceInfo | null;
  selectedAvatar: SelectedAvatar | null;
  currentTask: CurrentTask | null;
  setCurrentMusic: (m: CurrentMusic | null) => void;
  setSelectedSegment: (s: { start: number; end: number } | null) => void;
  setSlice: (s: SliceInfo | null) => void;
  setSelectedAvatar: (a: SelectedAvatar | null) => void;
  setCurrentTask: (t: CurrentTask | null) => void;
  reset: () => void;
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      currentMusic: null,
      selectedSegment: null,
      slice: null,
      selectedAvatar: null,
      currentTask: null,
      setCurrentMusic: (m) =>
        set({
          currentMusic: m,
          selectedSegment: m?.chorus
            ? { start: m.chorus.start_sec, end: m.chorus.end_sec }
            : null,
          slice: null,
        }),
      setSelectedSegment: (s) => set({ selectedSegment: s }),
      setSlice: (s) => set({ slice: s }),
      setSelectedAvatar: (a) => set({ selectedAvatar: a }),
      setCurrentTask: (t) => set({ currentTask: t }),
      reset: () =>
        set({
          currentMusic: null,
          selectedSegment: null,
          slice: null,
          selectedAvatar: null,
          currentTask: null,
        }),
    }),
    {
      name: "sdh-app-state",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        selectedAvatar: state.selectedAvatar,
        currentMusic: state.currentMusic,
        selectedSegment: state.selectedSegment,
        slice: state.slice,
      }),
    },
  ),
);
