import { create } from 'zustand';

interface ChatState {
  threadId: string | null;
  setThreadId: (id: string) => void;
  isProcessing: boolean;
  setIsProcessing: (status: boolean) => void;
  activeAgent: string | null;
  setActiveAgent: (target: string | null) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  threadId: null,
  setThreadId: (id) => set({ threadId: id }),
  isProcessing: false,
  setIsProcessing: (status) => set({ isProcessing: status }),
  activeAgent: null,
  setActiveAgent: (target) => set({ activeAgent: target }),
}));
