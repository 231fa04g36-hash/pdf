import { delay } from './mockConfig';

export let mockConversationsList = [
  {
    id: 'conv-1',
    title: 'React 18 Concurrent Rendering',
    updatedAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 'conv-2',
    title: 'FastAPI Stream Chunking Guide',
    updatedAt: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 'conv-3',
    title: 'ChromaDB Embedding Optimizations',
    updatedAt: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 'conv-4',
    title: 'LangChain Agent Chains Parser',
    updatedAt: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
  },
];

export const mockConversationsMessages = {
  'conv-1': [
    {
      id: 'msg-1-1',
      role: 'user',
      content: 'Can you explain how React 18 concurrent rendering works?',
    },
    {
      id: 'msg-1-2',
      role: 'assistant',
      content:
        'React 18 concurrent rendering allows React to interrupt ongoing renders to handle high-priority user actions, ensuring that the main thread stays responsive even during heavy updates. Behind the scenes, it manages fiber priorities and yields back control to the browser paint scheduler.',
      citations: [
        {
          page: 2,
          snippet:
            'Concurrent rendering enables React to prepare multiple versions of UI at the same time...',
        },
      ],
    },
  ],
  'conv-2': [
    {
      id: 'msg-2-1',
      role: 'user',
      content: 'How do I configure FastAPI streaming endpoints?',
    },
    {
      id: 'msg-2-2',
      role: 'assistant',
      content:
        'In FastAPI, you can return a StreamingResponse, which accepts a generator function yielding chunks of text or bytes. This is commonly paired with SSE data streams and LLM completions.',
      citations: [
        {
          page: 1,
          snippet:
            'FastAPI StreamingResponse provides an async channel to push bytes or strings chunk-by-chunk...',
        },
      ],
    },
  ],
  'conv-3': [
    {
      id: 'msg-3-1',
      role: 'user',
      content: 'How do I optimize ChromaDB query latency?',
    },
    {
      id: 'msg-3-2',
      role: 'assistant',
      content:
        'ChromaDB query latency can be optimized by batching vectors, using index configurations like HNSW, and optimizing the chunk sizes of documents.',
      citations: [
        {
          page: 4,
          snippet:
            'ChromaDB searches are optimized via approximate nearest neighbor indexing hierarchies...',
        },
      ],
    },
  ],
  'conv-4': [
    {
      id: 'msg-4-1',
      role: 'user',
      content: 'How do agents work in LangChain?',
    },
    {
      id: 'msg-4-2',
      role: 'assistant',
      content:
        'LangChain agents use a reasoning loop (like ReAct) to dynamically determine which tools to call based on input prompts.',
      citations: [
        {
          page: 3,
          snippet:
            'Agents translate thoughts, actions, and observations recursively using ReAct prompts...',
        },
      ],
    },
  ],
};

export const getConversations = async () => {
  await delay(300);
  return [...mockConversationsList].sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
};

export const getMessages = async (id) => {
  await delay(300);
  return mockConversationsMessages[id] || [];
};

export const renameConversation = async (id, title) => {
  await delay(300);
  let found = false;
  mockConversationsList = mockConversationsList.map((c) => {
    if (c.id === id) {
      found = true;
      return { ...c, title, updatedAt: new Date().toISOString() };
    }
    return c;
  });
  if (!found) {
    throw new Error('Conversation not found');
  }
  return { success: true };
};

export const createConversation = async (title, initialMessages = []) => {
  await delay(300);
  const newConv = {
    id: 'conv-' + Math.random().toString(36).substring(2, 11),
    title,
    updatedAt: new Date().toISOString(),
  };
  mockConversationsList.push(newConv);
  mockConversationsMessages[newConv.id] = initialMessages;
  return newConv;
};

export const deleteConversation = async (id) => {
  await delay(300);
  mockConversationsList = mockConversationsList.filter((c) => c.id !== id);
  delete mockConversationsMessages[id];
  return { success: true };
};

export const clearAllConversations = async () => {
  await delay(300);
  mockConversationsList = [];
  // Clear messages dictionary
  for (const prop in mockConversationsMessages) {
    if (Object.prototype.hasOwnProperty.call(mockConversationsMessages, prop)) {
      delete mockConversationsMessages[prop];
    }
  }
  return { success: true };
};
