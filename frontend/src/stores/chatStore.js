import { create } from 'zustand';

export const useChatStore = create((set) => ({
  messages: [],
  isStreaming: false,
  setMessages: (messages) => set({ messages }),
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  setStreaming: (isStreaming) => set({ isStreaming }),
  clearMessages: () => set({ messages: [] }),
  updateLastMessageContent: (content) =>
    set((state) => {
      const messages = [...state.messages];
      if (messages.length > 0 && messages[messages.length - 1].role === 'assistant') {
        messages[messages.length - 1].content = content;
      }
      return { messages };
    }),
  updateLastMessageCitations: (citations) =>
    set((state) => {
      const messages = [...state.messages];
      if (messages.length > 0 && messages[messages.length - 1].role === 'assistant') {
        messages[messages.length - 1].citations = citations;
      }
      return { messages };
    }),
  updateLastMessageError: ({ isError, errorType, content }) =>
    set((state) => {
      const messages = [...state.messages];
      if (messages.length > 0 && messages[messages.length - 1].role === 'assistant') {
        messages[messages.length - 1].isError = isError;
        messages[messages.length - 1].errorType = errorType;
        messages[messages.length - 1].content = content;
      }
      return { messages };
    }),
}));
