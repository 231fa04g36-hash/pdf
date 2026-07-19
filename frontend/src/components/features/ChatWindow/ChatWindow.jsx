import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Send, Copy, RotateCcw, HelpCircle, AlertOctagon, ArrowDown } from 'lucide-react';
import { useChatStore } from '../../../stores/chatStore';
import { useChatStream } from '../../../hooks/useChatStream';
import { useConversationStore } from '../../../stores/conversationStore';
import { showSuccessToast } from '../../../utils/toast';
import Avatar from '../../shared/Avatar/Avatar';
import Button from '../../shared/Button/Button';
import SourceCitation from '../../chat/SourceCitation/SourceCitation';
import styles from './ChatWindow.module.css';

const SUGGESTIONS = [
  'How does Retrieval-Augmented Generation (RAG) work?',
  'How does anonymous session mapping and linking work?',
  'What are vector databases and how is ChromaDB used?',
];

const preprocessMessageContent = (content) => {
  if (!content) return '';
  // Convert [Page X] or Page X or Page X-Y (with space/colon) to standard markdown link [Page X](#citation-X)
  return content.replace(/(?:\[)?\b[Pp]age(?:\s+|\s*:\s*)(\d+(?:\s*-\s*\d+)?)\b(?:\])?/g, (match, p1) => {
    // Clean spaces from the anchor URL, e.g. "6 -7" to "6-7"
    const anchor = p1.replace(/\s+/g, '');
    return `[Page ${p1}](#citation-${anchor})`;
  });
};

const findMatchingCitation = (citations, pageStr) => {
  if (!citations) return null;
  const cleanPageStr = pageStr.replace(/\s+/g, '');
  
  // Try exact string match first
  let found = citations.find((c) => String(c.page).replace(/\s+/g, '') === cleanPageStr);
  if (found) return found;

  // Try parsing pageStr as integer
  const pageNum = parseInt(cleanPageStr, 10);
  if (isNaN(pageNum)) return null;

  // Match by checking if pageNum falls within the citation's page or range
  return citations.find((c) => {
    const cPage = c.page;
    if (typeof cPage === 'number') {
      return cPage === pageNum;
    }
    if (typeof cPage === 'string') {
      const cleanCPage = cPage.replace(/\s+/g, '');
      if (cleanCPage === cleanPageStr) return true;

      // Extract first number or check range
      const parts = cleanCPage.split('-').map(p => parseInt(p, 10));
      if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
        return pageNum >= parts[0] && pageNum <= parts[1];
      }
      
      const singleNum = parseInt(cleanCPage, 10);
      return singleNum === pageNum;
    }
    return false;
  });
};

export default function ChatWindow() {
  const { messages, isStreaming, setMessages, clearMessages } = useChatStore();
  const { streamChat } = useChatStream();
  const { setActiveCitation } = useConversationStore();

  const [inputVal, setInputVal] = useState('');
  const [isInputFocused, setIsInputFocused] = useState(false);
  const [isScrolledUp, setIsScrolledUp] = useState(false);
  const [devErrorType, setDevErrorType] = useState('none');

  const scrollContainerRef = useRef(null);
  const textareaRef = useRef(null);
  const messagesEndRef = useRef(null);

  const isMock = import.meta.env.VITE_USE_MOCK_API === 'true';

  // Auto-scroll logic to stay aligned at the bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // OLD: auto-scroll triggered once per new message added to the array, but 
  // did not re-trigger on every token appended during an active stream — 
  // could cause the view to fall behind a long streaming answer. Replaced 
  // below to also scroll on each streamed token update, still respecting 
  // the existing "user scrolled up, stop auto-scrolling" behavior.
  const lastMessageContent = messages[messages.length - 1]?.content;

  useEffect(() => {
    if (!isScrolledUp) {
      scrollToBottom();
    }
  }, [messages, isStreaming, isScrolledUp, lastMessageContent]);

  // Track scrolling actions to enable scroll locking
  const handleScroll = () => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const isAtBottom = el.scrollHeight - el.scrollTop <= el.clientHeight + 60;
    setIsScrolledUp(!isAtBottom);
  };

  const handleSend = async (textToSend) => {
    const text = textToSend || inputVal;
    if (!text.trim() || isStreaming) return;

    setInputVal('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    setIsScrolledUp(false);
    await streamChat(text, devErrorType !== 'none' ? devErrorType : null);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleTextareaInput = (e) => {
    e.target.style.height = 'auto';
    e.target.style.height = `${e.target.scrollHeight}px`;
  };

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
    showSuccessToast('Response copied to clipboard!');
  };

  const handleRegenerate = () => {
    if (messages.length < 2) return;
    const lastMsg = messages[messages.length - 1];
    const prevMsg = messages[messages.length - 2];

    if (lastMsg.role === 'assistant' && prevMsg.role === 'user') {
      const messagesClone = messages.slice(0, messages.length - 2);
      setMessages(messagesClone);
      setIsScrolledUp(false);
      streamChat(prevMsg.content, devErrorType !== 'none' ? devErrorType : null);
    }
  };

  return (
    <div className={styles.chatContainer}>
      {/* Scrollable message feed */}
      <div className={styles.messagesList} ref={scrollContainerRef} onScroll={handleScroll}>
        {messages.length === 0 ? (
          <div className={styles.emptyState}>
            <div className={styles.emptyTitle}>Ask anything about your PDF</div>
            <div className={styles.emptySub}>
              Select a suggested question below or input your own query to start parsing data.
            </div>
            <div className={styles.suggestionsGrid}>
              {SUGGESTIONS.map((s, idx) => (
                <button
                  key={idx}
                  type="button"
                  className={styles.suggestionChip}
                  onClick={() => handleSend(s)}
                  disabled={isStreaming}
                >
                  <span>{s}</span>
                  <HelpCircle size={16} style={{ opacity: 0.6 }} />
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, index) => {
            const isUser = msg.role === 'user';
            const isLast = index === messages.length - 1;

            if (msg.isError) {
              return (
                <div key={msg.id} className={styles.errorBubble}>
                  <div className={styles.errorHeader}>
                    <AlertOctagon size={18} />
                    <span>Error ({msg.errorType})</span>
                  </div>
                  <div className={styles.errorContent}>{msg.content}</div>
                  <div style={{ alignSelf: 'flex-start' }}>
                    <Button variant="danger" size="sm" onClick={handleRegenerate}>
                      <RotateCcw size={14} style={{ marginRight: '6px' }} />
                      Retry Request
                    </Button>
                  </div>
                </div>
              );
            }

            return (
              <div
                key={msg.id}
                className={`${styles.messageRow} ${isUser ? styles.userRow : styles.assistantRow}`}
              >
                {!isUser && <Avatar name="AI" variant="assistant" size="sm" />}
                <div
                  className={`${styles.messageBubble} ${isUser ? styles.userBubble : styles.assistantBubble}`}
                >
                  {isUser ? (
                    <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                  ) : msg.content === '' && isStreaming && isLast ? (
                    <div className={styles.typingIndicator}>
                      <div className={styles.typingDot} />
                      <div className={styles.typingDot} />
                      <div className={styles.typingDot} />
                    </div>
                  ) : (
                    <div>
                      {/* OLD: ReactMarkdown rendered without the GFM (GitHub Flavored Markdown) 
                      // plugin, so markdown tables generated by the LLM displayed as raw pipe-
                      // delimited text instead of an actual table. Replaced below by adding 
                      // remark-gfm.
                      // <ReactMarkdown
                      //   components={{
                      // */}
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          a: ({ href, children, ...props }) => {
                            if (href && href.startsWith('#citation-')) {
                              const pageStr = decodeURIComponent(href.replace('#citation-', ''));
                              const matchedCitation = findMatchingCitation(msg.citations, pageStr);
                              const citation = matchedCitation || {
                                page: pageStr,
                                snippet: '',
                              };
                              return (
                                <a
                                  href={href}
                                  onClick={(e) => {
                                    e.preventDefault();
                                    setActiveCitation(citation);
                                  }}
                                  className={styles.inlineCitationLink}
                                  {...props}
                                >
                                  {children}
                                </a>
                              );
                            }
                            return <a href={href} target="_blank" rel="noopener noreferrer" {...props} />;
                          },
                        }}
                      >
                        {preprocessMessageContent(msg.content)}
                      </ReactMarkdown>

                      {/* Display page citation pills */}
                      <SourceCitation citations={msg.citations || []} />

                      {/* Floating actions on hover */}
                      <div className={styles.bubbleActions}>
                        <button
                          type="button"
                          className={styles.actionIconBtn}
                          onClick={() => handleCopy(msg.content)}
                          title="Copy Answer"
                        >
                          <Copy size={14} />
                        </button>
                        {isLast && !isStreaming && (
                          <button
                            type="button"
                            className={styles.actionTextBtn}
                            onClick={handleRegenerate}
                            title="Regenerate Response"
                          >
                            <RotateCcw size={12} />
                            <span>Regenerate</span>
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
                {isUser && <Avatar name="User" variant="user" size="sm" />}
              </div>
            );
          })
        )}
      </div>

      {/* Floating Jump to latest scroll indicator */}
      {isScrolledUp && isStreaming && (
        <button type="button" className={styles.jumpBtn} onClick={scrollToBottom}>
          <ArrowDown size={14} />
          <span>Jump to latest</span>
        </button>
      )}

      {/* Bottom Pinned Input panel */}
      <div className={styles.inputPanel}>
        <div className={`${styles.inputWrapper} ${isInputFocused ? styles.inputWrapperFocus : ''}`}>
          <textarea
            ref={textareaRef}
            rows={1}
            className={styles.textarea}
            placeholder={isStreaming ? 'AI is generating...' : 'Ask a question...'}
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={handleKeyDown}
            onInput={handleTextareaInput}
            onFocus={() => setIsInputFocused(true)}
            onBlur={() => setIsInputFocused(false)}
            disabled={isStreaming}
          />
          <button
            type="button"
            className={styles.sendBtn}
            onClick={() => handleSend()}
            disabled={!inputVal.trim() || isStreaming}
            aria-label="Send message"
          >
            <Send size={16} />
          </button>
        </div>

        {/* Mock Mode Diagnostic dropdown */}
        {isMock && !isStreaming && (
          <div className={styles.devPanel}>
            <span>[Dev Only] Simulated LLM Outcome:</span>
            <select
              className={styles.devSelect}
              value={devErrorType}
              onChange={(e) => setDevErrorType(e.target.value)}
            >
              <option value="none">Standard API Stream Success</option>
              <option value="rate_limit">Simulate Rate Limit Failure</option>
              <option value="timeout">Simulate Timeout Failure</option>
              <option value="server_error">Simulate Server Failure</option>
            </select>
            <button
              type="button"
              onClick={clearMessages}
              style={{
                marginLeft: 'auto',
                background: 'transparent',
                border: 'none',
                color: 'var(--color-danger)',
                cursor: 'pointer',
              }}
            >
              Clear Conversation History
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
