// OLD: Simple imports without firebase auth or uuid.
// import { isMockEnabled } from './mocks/mockConfig';
// import { mockChatStream } from './mocks/mockChat';

// NEW: Imports updated to include uuid and auth client to support token generation and request payload schema
import { v4 as uuidv4 } from 'uuid';
import { isMockEnabled } from './mocks/mockConfig';
import { mockChatStream } from './mocks/mockChat';
import { auth } from './firebase';

// OLD: sendChatRequest function that sends only question text in a post request and parses streaming chunks without session context.
// export const sendChatRequest = async (question, onToken, onComplete, errorType = null) => {
//   if (isMockEnabled()) {
//     return mockChatStream(question, onToken, onComplete, errorType);
//   }
//
//   const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/chat`, {
//     method: 'POST',
//     headers: {
//       'Content-Type': 'application/json',
//     },
//     body: JSON.stringify({ question }),
//   });
//
//   if (!response.ok) {
//     let errMsg = `HTTP Error ${response.status}`;
//     const isRate = response.status === 429;
//     const isTimeout = response.status === 504;
//     try {
//       const errJson = await response.json();
//       if (errJson.message) {
//         errMsg = errJson.message;
//       }
//     } catch {
//       // Fallback
//     }
//
//     throw {
//       isError: true,
//       errorType: isRate ? 'rate_limit' : isTimeout ? 'timeout' : 'server_error',
//       message: errMsg,
//     };
//   }
//
//   if (!response.body) {
//     throw new Error('Response body is empty or unreadable');
//   }
//
//   const reader = response.body.getReader();
//   const decoder = new TextDecoder('utf-8');
//   let done = false;
//   let partialChunk = '';
//   let finalCitations = [];
//   let accumulatedContent = '';
//
//   while (!done) {
//     const { value, done: readerDone } = await reader.read();
//     done = readerDone;
//     if (value) {
//       const text = decoder.decode(value, { stream: !done });
//       const rawLines = (partialChunk + text).split('\n');
//       partialChunk = rawLines.pop() || '';
//
//       for (const line of rawLines) {
//         const trimmed = line.trim();
//         if (!trimmed) continue;
//
//         let dataString = trimmed;
//         if (trimmed.startsWith('data:')) {
//           dataString = trimmed.replace('data:', '').trim();
//         }
//
//         if (dataString === '[DONE]') {
//           continue;
//         }
//
//         try {
//           const parsed = JSON.parse(dataString);
//           if (parsed.token) {
//             accumulatedContent += parsed.token;
//             onToken(parsed.token);
//           }
//           if (parsed.citations) {
//             finalCitations = parsed.citations;
//           }
//           if (parsed.error) {
//             throw {
//               isError: true,
//               errorType: 'server_error',
//               message: parsed.error,
//             };
//           }
//         } catch (e) {
//           if (e.isError) {
//             throw e;
//           }
//         }
//       }
//     }
//   }
//
//   onComplete({
//     content: accumulatedContent,
//     citations: finalCitations,
//   });
// };

// NEW: sendChatRequest function that attaches session headers, JWT token, formats correct payload, and passes back conversationId
export const sendChatRequest = async (
  question,
  onToken,
  onComplete,
  documentId,
  conversationId = null,
  errorType = null
) => {
  if (isMockEnabled()) {
    return mockChatStream(question, onToken, onComplete, errorType);
  }

  const headers = {
    'Content-Type': 'application/json',
  };

  // Helper function to extract session cookie for anonymous users
  const getCookie = (name) => {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
  };

  // 1. Attach guest session ID if present
  const sId = getCookie('session_id');
  if (sId) {
    headers['X-Session-Id'] = sId;
  }

  // 2. Attach Authorization token if user is signed in
  if (auth && auth.currentUser) {
    try {
      const token = await auth.currentUser.getIdToken();
      headers['Authorization'] = `Bearer ${token}`;
    } catch (err) {
      console.error('Error attaching auth token to fetch request:', err);
    }
  }

  // 3. Construct payload matching FastAPI ChatRequest schema
  const payload = {
    question,
    documentId: documentId,
    conversationId: conversationId || null,
    requestId: uuidv4(),
  };

  const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errMsg = `HTTP Error ${response.status}`;
    const isRate = response.status === 429;
    const isTimeout = response.status === 504;
    try {
      const errJson = await response.json();
      if (errJson.message) {
        errMsg = errJson.message;
      }
    } catch {
      // Fallback
    }

    throw {
      isError: true,
      errorType: isRate ? 'rate_limit' : isTimeout ? 'timeout' : 'server_error',
      message: errMsg,
    };
  }

  if (!response.body) {
    throw new Error('Response body is empty or unreadable');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let done = false;
  let partialChunk = '';
  let finalCitations = [];
  let accumulatedContent = '';
  let streamConversationId = '';

  while (!done) {
    const { value, done: readerDone } = await reader.read();
    done = readerDone;
    if (value) {
      const text = decoder.decode(value, { stream: !done });
      const rawLines = (partialChunk + text).split('\n');
      partialChunk = rawLines.pop() || '';

      for (const line of rawLines) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        let dataString = trimmed;
        if (trimmed.startsWith('data:')) {
          dataString = trimmed.replace('data:', '').trim();
        }

        if (dataString === '[DONE]') {
          continue;
        }

        try {
          const parsed = JSON.parse(dataString);
          if (parsed.token) {
            accumulatedContent += parsed.token;
            onToken(parsed.token);
          }
          if (parsed.citations) {
            finalCitations = parsed.citations;
          }
          if (parsed.conversationId) {
            streamConversationId = parsed.conversationId;
          }
          if (parsed.error) {
            throw {
              isError: true,
              errorType: 'server_error',
              message: parsed.error,
            };
          }
        } catch (e) {
          if (e.isError) {
            throw e;
          }
        }
      }
    }
  }

  onComplete({
    content: accumulatedContent,
    citations: finalCitations,
    conversationId: streamConversationId,
  });
};
