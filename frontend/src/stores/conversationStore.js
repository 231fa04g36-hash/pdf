import { create } from 'zustand';

export const useConversationStore = create((set) => ({
  conversations: [],
  activeConversationId: null,
  activeDocument: null,
  uploadedDocuments: [],
  activeCitation: null,
  setConversations: (conversations) => set({ conversations }),
  setActiveConversationId: (activeConversationId) => set({ activeConversationId }),
  addConversation: (conversation) =>
    set((state) => ({ conversations: [conversation, ...state.conversations] })),
  deleteConversation: (id) =>
    set((state) => ({
      conversations: state.conversations.filter((c) => c.id !== id),
      activeConversationId: state.activeConversationId === id ? null : state.activeConversationId,
    })),
  deleteConversationOptimistic: (id) => {
    let deletedConv = null;
    let oldActiveId = null;
    set((state) => {
      deletedConv = state.conversations.find((c) => c.id === id);
      oldActiveId = state.activeConversationId;
      return {
        conversations: state.conversations.filter((c) => c.id !== id),
        activeConversationId: state.activeConversationId === id ? null : state.activeConversationId,
      };
    });
    // Return rollback function
    return () => {
      set((state) => {
        if (!deletedConv) return {};
        const exists = state.conversations.some((c) => c.id === id);
        const conversations = exists
          ? state.conversations
          : [...state.conversations, deletedConv].sort(
              (a, b) => new Date(b.updatedAt) - new Date(a.updatedAt)
            );
        return {
          conversations,
          activeConversationId: oldActiveId,
        };
      });
    };
  },
  clearConversationsOptimistic: () => {
    let oldConvs = [];
    let oldActiveId = null;
    set((state) => {
      oldConvs = state.conversations;
      oldActiveId = state.activeConversationId;
      return {
        conversations: [],
        activeConversationId: null,
      };
    });
    // Return rollback function
    return () => {
      set({
        conversations: oldConvs,
        activeConversationId: oldActiveId,
      });
    };
  },
  isLoadingConversations: false,
  setConversationsLoading: (isLoadingConversations) => set({ isLoadingConversations }),
  renameConversationOptimistic: (id, newTitle) => {
    let oldTitle = '';
    set((state) => {
      const conversations = state.conversations.map((c) => {
        if (c.id === id) {
          oldTitle = c.title;
          return { ...c, title: newTitle };
        }
        return c;
      });
      return { conversations };
    });
    // Return rollback function
    return () => {
      set((state) => {
        const conversations = state.conversations.map((c) => {
          if (c.id === id) return { ...c, title: oldTitle };
          return c;
        });
        return { conversations };
      });
    };
  },
  setActiveDocument: (activeDocument) => set({ activeDocument }),
  addUploadedDocument: (doc) =>
    set((state) => ({ uploadedDocuments: [doc, ...state.uploadedDocuments] })),
  setUploadedDocuments: (uploadedDocuments) => set({ uploadedDocuments }),
  setActiveCitation: (activeCitation) => set({ activeCitation }),
}));
