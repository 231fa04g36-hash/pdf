import api from './api';
import { isMockEnabled } from './mocks/mockConfig';
import * as mockConversations from './mocks/mockConversations';

export const getConversations = async () => {
  if (isMockEnabled()) {
    return mockConversations.getConversations();
  }
  const response = await api.get('/conversations');
  return response.data;
};

export const getMessages = async (id) => {
  if (isMockEnabled()) {
    return mockConversations.getMessages(id);
  }
  const response = await api.get(`/conversations/${id}/messages`);
  const messages = response.data || [];
  return messages.map((msg) => ({
    ...msg,
    citations: msg.citations || msg.sourceCitations || msg.source_citations || [],
  }));
};

export const renameConversation = async (id, title) => {
  if (isMockEnabled()) {
    return mockConversations.renameConversation(id, title);
  }
  const response = await api.patch(`/conversations/${id}`, { title });
  return response.data;
};

// OLD: Function to create a conversation on the backend via POST /conversations.
// export const createConversation = async (title, initialMessages = []) => {
//   if (isMockEnabled()) {
//     return mockConversations.createConversation(title, initialMessages);
//   }
//   const response = await api.post('/conversations', { title, messages: initialMessages });
//   return response.data;
// };

// NEW: Updated createConversation function which receives the backend-created realId and returns the conversation model directly for local store updates
export const createConversation = async (title, initialMessages = [], realId = null) => {
  if (isMockEnabled()) {
    return mockConversations.createConversation(title, initialMessages);
  }

  // Under real API mode, the conversation is implicitly created by the backend /chat service.
  // We return a mock-compatible object representation referencing the real backend ID.
  return {
    id: realId,
    title,
    updatedAt: new Date().toISOString(),
  };
};

export const deleteConversation = async (id) => {
  if (isMockEnabled()) {
    return mockConversations.deleteConversation(id);
  }
  const response = await api.delete(`/conversations/${id}`);
  return response.data;
};

export const clearAllConversations = async () => {
  if (isMockEnabled()) {
    return mockConversations.clearAllConversations();
  }
  const response = await api.delete('/conversations');
  return response.data;
};
