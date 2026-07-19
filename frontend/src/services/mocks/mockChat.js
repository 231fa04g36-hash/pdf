export const cannedAnswers = {
  rag: {
    content:
      'Retrieval-Augmented Generation (RAG) processes documents by first partitioning them into text chunks. These chunks are embedded into vectors using an embedding model and indexed in a vector store like ChromaDB. When a query is made, the vector database fetches the most semantically relevant text fragments, and the language model consolidates them into a grounded, cited answer.',
    citations: [
      {
        page: 2,
        snippet:
          'RAG works by chunking documents and vectorizing text segments for fast semantic search...',
      },
    ],
  },
  auth: {
    content:
      'This PDF Chatbot supports both Google Sign-In and anonymous free demo access. Anonymous sessions are generated using UUID session keys mirrored to cookies, preserving local history per tab. Authenticating with Google links this session token to persistent storage, preserving conversations across all devices.',
    citations: [
      {
        page: 5,
        snippet: 'Auth Context uses UUID sessions in document.cookie to enable free guest usage...',
      },
    ],
  },
  default: {
    content:
      'Based on the uploaded document, I found that the context describes a clean SaaS application layout. The design features a flexible sidebar drawer, a contextual PDF indicator, and responsive grid layouts. The system is designed to provide high-quality grounded question answering with inline sources.',
    citations: [
      {
        page: 1,
        snippet: 'The document describes a SaaS application layout with a fixed sidebar panel...',
      },
    ],
  },
};

export const mockChatStream = (question, onToken, onComplete, errorType = null) => {
  return new Promise((resolve, reject) => {
    // Simulating immediate error paths
    if (errorType === 'rate_limit') {
      setTimeout(() => {
        reject({
          isError: true,
          errorType: 'rate_limit',
          message: 'Too many requests. Please slow down and try again later.',
        });
      }, 500);
      return;
    }
    if (errorType === 'timeout') {
      setTimeout(() => {
        reject({
          isError: true,
          errorType: 'timeout',
          message: 'Request timed out. The model took too long to respond.',
        });
      }, 500);
      return;
    }
    if (errorType === 'server_error') {
      setTimeout(() => {
        reject({
          isError: true,
          errorType: 'server_error',
          message: 'Internal server error. The language model API failed to process the prompt.',
        });
      }, 500);
      return;
    }

    // Select canned answer based on keywords
    const lowerQuestion = question.toLowerCase();
    let selected = cannedAnswers.default;
    if (
      lowerQuestion.includes('rag') ||
      lowerQuestion.includes('how it works') ||
      lowerQuestion.includes('how does')
    ) {
      selected = cannedAnswers.rag;
    } else if (
      lowerQuestion.includes('auth') ||
      lowerQuestion.includes('cookie') ||
      lowerQuestion.includes('sign in') ||
      lowerQuestion.includes('google')
    ) {
      selected = cannedAnswers.auth;
    }

    const words = selected.content.split(' ');
    let index = 0;

    const interval = setInterval(() => {
      if (index < words.length) {
        const nextWord = words[index] + (index === words.length - 1 ? '' : ' ');
        onToken(nextWord);
        index++;
      } else {
        clearInterval(interval);
        onComplete({
          content: selected.content,
          citations: selected.citations,
        });
        resolve();
      }
    }, 80);
  });
};
