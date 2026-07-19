import { useState, useEffect, useRef } from 'react';
import { Outlet, useParams, useNavigate } from 'react-router-dom';
import { useConversationStore } from '../../../stores/conversationStore';
import { useAuth } from '../../../contexts/AuthContext';
import { useChatStore } from '../../../stores/chatStore';
import * as conversationService from '../../../services/conversationService';
import { showErrorToast } from '../../../utils/toast';
import PdfPageViewer from '../../pdf-viewer/PdfPageViewer/PdfPageViewer';
import Sidebar from './Sidebar';
import TopBar from './TopBar';
import styles from './AppLayout.module.css';

export default function AppLayout() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const { user, isAnonymous } = useAuth();
  const { messages, setMessages, clearMessages } = useChatStore();
  const {
    activeCitation,
    setActiveCitation,
    conversations,
    setActiveDocument,
    setConversations,
    setConversationsLoading,
    activeConversationId,
    setActiveConversationId,
  } = useConversationStore();

  const lastProcessedIdRef = useRef('INITIAL');

  // 1. Fetch conversations list when authenticated user signs in
  useEffect(() => {
    if (isAnonymous) {
      setConversations([]);
      return;
    }

    const fetchConvs = async () => {
      setConversationsLoading(true);
      try {
        const convList = await conversationService.getConversations();
        setConversations(convList);
      } catch (err) {
        console.error(err);
        showErrorToast('Failed to load conversations');
      } finally {
        setConversationsLoading(false);
      }
    };

    fetchConvs();
  }, [user, isAnonymous, setConversations, setConversationsLoading]);

  // 2. Synchronize active conversation messages when URL param shifts
  useEffect(() => {
    if (lastProcessedIdRef.current === conversationId) {
      return;
    }
    lastProcessedIdRef.current = conversationId;

    if (!conversationId) {
      setActiveConversationId(null);
      clearMessages();
      return;
    }

    // Skip refetching messages from the API if this conversation is already active 
    // and we already have messages loaded in the local store (e.g. after stream completion).
    if (activeConversationId === conversationId && messages.length > 0) {
      return;
    }

    const loadMessages = async () => {
      setActiveConversationId(conversationId);
      try {
        const msgs = await conversationService.getMessages(conversationId);
        setMessages(msgs);
      } catch (err) {
        console.error(err);
        showErrorToast('Failed to load conversation history');
        navigate('/app');
      }
    };

    loadMessages();
  }, [conversationId, activeConversationId, messages.length, setActiveConversationId, clearMessages, setMessages, navigate]);

  // 3. Synchronize active document context when active conversation changes
  useEffect(() => {
    if (!conversationId || conversations.length === 0) {
      return;
    }

    const currentConv = conversations.find((c) => c.id === conversationId);
    if (currentConv && currentConv.document) {
      const doc = currentConv.document;
      setActiveDocument({
        document_id: doc.documentId || doc.document_id || doc.id,
        filename: doc.filename,
        page_count: doc.pageCount !== undefined ? doc.pageCount : doc.page_count,
        ocr_triggered: doc.ocrTriggered !== undefined ? doc.ocrTriggered : doc.ocr_triggered,
      });
    }
  }, [conversationId, conversations, setActiveDocument]);

  const toggleSidebar = () => {
    setIsSidebarOpen((prev) => !prev);
  };

  const closeSidebar = () => {
    setIsSidebarOpen(false);
  };

  const closeDrawer = () => {
    setActiveCitation(null);
  };

  return (
    <div className={styles.layout}>
      {/* Sidebar overlay backdrop for mobile */}
      {isSidebarOpen ? <div className={styles.backdrop} onClick={closeSidebar} /> : null}

      {/* Collapsible Sidebar */}
      <Sidebar isOpen={isSidebarOpen} onClose={closeSidebar} />

      {/* Main Content Area */}
      <div className={styles.mainPanel}>
        <TopBar onToggleSidebar={toggleSidebar} />
        <div className={styles.splitLayout}>
          <div className={styles.contentWrapper}>
            <Outlet />
          </div>
          {activeCitation ? (
            <div className={styles.pdfPanel}>
              <PdfPageViewer citation={activeCitation} onClose={closeDrawer} />
            </div>
          ) : null}
        </div>
      </div>

      {/* Side Citation Viewer Drawer Backdrop (only used on mobile) */}
      {activeCitation ? (
        <div className={styles.drawerBackdrop} onClick={closeDrawer} />
      ) : null}
    </div>
  );
}
