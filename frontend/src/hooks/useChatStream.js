import { useNavigate } from 'react-router-dom';
import { useChatStore } from '../stores/chatStore';
import { useConversationStore } from '../stores/conversationStore';
import { sendChatRequest } from '../services/chatService';
import * as conversationService from '../services/conversationService';

export const useChatStream = () => {
  const navigate = useNavigate();
  const {
    addMessage,
    setStreaming,
    updateLastMessageContent,
    updateLastMessageCitations,
    updateLastMessageError,
  } = useChatStore();

  // OLD: streamChat function that triggers sendChatRequest without activeDocument.id or activeConversationId, and without capturing the backend's conversationId on completion.
  //   const { activeConversationId, setActiveConversationId, addConversation } = useConversationStore();
  //
  //   const streamChat = async (question, errorType = null) => {
  //     setStreaming(true);
  //
  //     // 1. Add User Message
  //     const userMsgId = 'user-' + Date.now();
  //     addMessage({
  //       id: userMsgId,
  //       role: 'user',
  //       content: question,
  //     });
  //
  //     // 2. Add Assistant Placeholder Message
  //     const assistantMsgId = 'assistant-' + (Date.now() + 1);
  //     addMessage({
  //       id: assistantMsgId,
  //       role: 'assistant',
  //       content: '',
  //       citations: [],
  //       isError: false,
  //       errorType: null,
  //     });
  //
  //     let accumulatedContent = '';
  //     let finalContent = '';
  //     let finalCitations = [];
  //
  //     try {
  //       await sendChatRequest(
  //         question,
  //         (token) => {
  //           accumulatedContent += token;
  //           updateLastMessageContent(accumulatedContent);
  //         },
  //         ({ content, citations }) => {
  //           finalContent = content;
  //           finalCitations = citations;
  //           updateLastMessageContent(content);
  //           updateLastMessageCitations(citations);
  //           setStreaming(false);
  //         },
  //         errorType
  //       );
  //
  //       // Create conversation context if it's the first message and query is successful
  //       if (!activeConversationId) {
  //         const title = question.substring(0, 40) + (question.length > 40 ? '...' : '');
  //         const initialMessages = [
  //           { id: userMsgId, role: 'user', content: question },
  //           {
  //             id: assistantMsgId,
  //             role: 'assistant',
  //             content: finalContent,
  //             citations: finalCitations,
  //           },
  //         ];
  //         const newConv = await conversationService.createConversation(title, initialMessages);
  //         addConversation(newConv);
  //         setActiveConversationId(newConv.id);
  //         navigate(`/app/${newConv.id}`);
  //       }
  //     } catch (err) {
  //       console.error(err);
  //       updateLastMessageError({
  //         isError: true,
  //         errorType: err.errorType || 'server_error',
  //         content: err.message || 'An unexpected server error occurred.',
  //       });
  //       setStreaming(false);
  //     }
  //   };

  // NEW: Updated streamChat implementation retrieving activeDocument, passing documentId and conversationId to backend, and linking local store with conversationId
  const { activeConversationId, setActiveConversationId, addConversation, activeDocument } =
    useConversationStore();

  const streamChat = async (question, errorType = null) => {
    setStreaming(true);

    // 1. Add User Message
    const userMsgId = 'user-' + Date.now();
    addMessage({
      id: userMsgId,
      role: 'user',
      content: question,
    });

    // 2. Add Assistant Placeholder Message
    const assistantMsgId = 'assistant-' + (Date.now() + 1);
    addMessage({
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      citations: [],
      isError: false,
      errorType: null,
    });

    let accumulatedContent = '';
    let finalContent = '';
    let finalCitations = [];
    let streamConversationId = '';

    try {
      // Pass required activeDocument.id and optional activeConversationId to sendChatRequest
      await sendChatRequest(
        question,
        (token) => {
          accumulatedContent += token;
          updateLastMessageContent(accumulatedContent);
        },
        ({ content, citations, conversationId }) => {
          finalContent = content;
          finalCitations = citations;
          streamConversationId = conversationId;
          updateLastMessageContent(content);
          updateLastMessageCitations(citations);
          setStreaming(false);
        },
        activeDocument?.document_id,
        activeConversationId,
        errorType
      );

      // Create conversation context if it's the first message and query is successful
      if (!activeConversationId) {
        const title = question.substring(0, 40) + (question.length > 40 ? '...' : '');
        const initialMessages = [
          { id: userMsgId, role: 'user', content: question },
          {
            id: assistantMsgId,
            role: 'assistant',
            content: finalContent,
            citations: finalCitations,
          },
        ];
        // Pass streamConversationId returned from backend to store it in local store conversation metadata
        const newConv = await conversationService.createConversation(
          title,
          initialMessages,
          streamConversationId
        );
        addConversation(newConv);
        setActiveConversationId(newConv.id);
        navigate(`/app/${newConv.id}`);
      }
    } catch (err) {
      console.error(err);
      updateLastMessageError({
        isError: true,
        errorType: err.errorType || 'server_error',
        content: err.message || 'An unexpected server error occurred.',
      });
      setStreaming(false);
    }
  };

  return { streamChat };
};
