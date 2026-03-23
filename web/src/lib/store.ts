import { create } from 'zustand';

interface ChatState {
  threadId: string | null;
  setThreadId: (id: string) => void;
  isProcessing: boolean;
  setIsProcessing: (status: boolean) => void;
  activeAgent: string | null;
  setActiveAgent: (target: string | null) => void;
  streamingBuffer: string;
  appendStreamingDelta: (delta: string) => void;
  resetStreamingBuffer: () => void;
  /** Server-sent lifecycle line (e.g. tool/Gmail in progress) before first model token. */
  streamingPhase: string | null;
  setStreamingPhase: (text: string | null) => void;
  lastSheetUploadId: string | null;
  setLastSheetUploadId: (id: string | null) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  threadId: null,
  setThreadId: (id) => set({ threadId: id }),
  isProcessing: false,
  setIsProcessing: (status) => set({ isProcessing: status }),
  activeAgent: null,
  setActiveAgent: (target) => set({ activeAgent: target }),
  streamingBuffer: "",
  appendStreamingDelta: (delta) =>
    set((state) => ({ streamingBuffer: state.streamingBuffer + delta })),
  resetStreamingBuffer: () => set({ streamingBuffer: "" }),
  streamingPhase: null,
  setStreamingPhase: (text) => set({ streamingPhase: text }),
  lastSheetUploadId: null,
  setLastSheetUploadId: (id) => set({ lastSheetUploadId: id }),
}));
