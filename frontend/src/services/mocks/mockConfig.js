// Helper utility for mocking API latency
export const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export const isMockEnabled = () => {
  return import.meta.env.VITE_USE_MOCK_API === 'true';
};
