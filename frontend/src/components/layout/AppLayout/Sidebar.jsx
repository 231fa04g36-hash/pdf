import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import PropTypes from 'prop-types';
import { FileText, X, Plus, File, Pencil, Sparkles, Trash2, MoreVertical } from 'lucide-react';
import { useConversationStore } from '../../../stores/conversationStore';
import { useAuth } from '../../../contexts/AuthContext';
import { useChatStore } from '../../../stores/chatStore';
import * as conversationService from '../../../services/conversationService';
import { formatRelativeTime } from '../../../utils/time';
import { showSuccessToast, showErrorToast } from '../../../utils/toast';
import Button from '../../shared/Button/Button';
import ConfirmModal from '../../shared/Modal/ConfirmModal';
import Modal from '../../shared/Modal/Modal';
import styles from './Sidebar.module.css';

export default function Sidebar({ isOpen, onClose }) {
  const navigate = useNavigate();
  const { isAnonymous } = useAuth();
  const { clearMessages } = useChatStore();
  const {
    conversations,
    activeConversationId,
    setActiveConversationId,
    uploadedDocuments,
    activeDocument,
    setActiveDocument,
    isLoadingConversations,
    renameConversationOptimistic,
    deleteConversationOptimistic,
    clearConversationsOptimistic,
  } = useConversationStore();

  const [editingConvId, setEditingConvId] = useState(null);
  const [renameValue, setRenameValue] = useState('');

  // Settings overflow states
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // Deletion modals states
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [selectedConvId, setSelectedConvId] = useState(null);
  const [isDeleteLoading, setIsDeleteLoading] = useState(false);

  // Bulk clear states
  const [isClearAllModalOpen, setIsClearAllModalOpen] = useState(false);
  const [confirmClearText, setConfirmClearText] = useState('');
  const [isClearAllLoading, setIsClearAllLoading] = useState(false);

  const inputRef = useRef(null);
  const settingsRef = useRef(null);

  // Focus the input element when entering rename mode
  useEffect(() => {
    if (editingConvId && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingConvId]);

  // Click outside to close settings dropdown menu
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (settingsRef.current && !settingsRef.current.contains(event.target)) {
        setIsSettingsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleNewChat = () => {
    setActiveConversationId(null);
    setActiveDocument(null);
    navigate('/app');
    onClose();
  };

  const startRename = (conv, e) => {
    e.stopPropagation();
    setEditingConvId(conv.id);
    setRenameValue(conv.title);
  };

  const handleRenameSubmit = async (convId) => {
    if (!renameValue.trim()) {
      setEditingConvId(null);
      return;
    }
    setEditingConvId(null);

    const rollback = renameConversationOptimistic(convId, renameValue);
    try {
      await conversationService.renameConversation(convId, renameValue);
      showSuccessToast('Conversation renamed');
    } catch (err) {
      console.error(err);
      rollback();
      showErrorToast('Failed to rename conversation');
    }
  };

  const handleRenameKeyDown = (e, convId) => {
    if (e.key === 'Enter') {
      handleRenameSubmit(convId);
    } else if (e.key === 'Escape') {
      setEditingConvId(null);
    }
  };

  // Open single delete confirmation modal
  const openDeleteModal = (convId, e) => {
    e.stopPropagation();
    setSelectedConvId(convId);
    setIsDeleteModalOpen(true);
  };

  // Execute single conversation deletion
  const handleDeleteConfirm = async () => {
    if (!selectedConvId) return;
    setIsDeleteLoading(true);

    const isCurrentActive = activeConversationId === selectedConvId;
    const rollback = deleteConversationOptimistic(selectedConvId);

    if (isCurrentActive) {
      clearMessages();
      navigate('/app');
    }

    try {
      await conversationService.deleteConversation(selectedConvId);
      showSuccessToast('Conversation deleted');
    } catch (err) {
      console.error(err);
      rollback();
      showErrorToast('Failed to delete conversation');
    } finally {
      setIsDeleteLoading(false);
      setIsDeleteModalOpen(false);
      setSelectedConvId(null);
    }
  };

  // Execute bulk deletion of all conversations
  const handleClearAllConfirm = async () => {
    if (confirmClearText.toLowerCase() !== 'delete') return;
    setIsClearAllLoading(true);

    const rollback = clearConversationsOptimistic();
    // Redirect and clear chatStore immediately
    clearMessages();
    navigate('/app');

    try {
      await conversationService.clearAllConversations();
      showSuccessToast('All conversations cleared');
    } catch (err) {
      console.error(err);
      rollback();
      showErrorToast('Failed to clear conversations');
    } finally {
      setIsClearAllLoading(false);
      setIsClearAllModalOpen(false);
      setConfirmClearText('');
    }
  };

  const sidebarClass = `${styles.sidebar} ${isOpen ? styles.open : ''}`;

  return (
    <aside className={sidebarClass}>
      <div className={styles.topSection}>
        <div className={styles.mobileHeader}>
          <div className={styles.sidebarTitle}>
            <FileText className={styles.logoIcon} size={20} />
            <span>PDF Chatbot</span>
          </div>
          <button
            type="button"
            className={styles.closeBtn}
            onClick={onClose}
            aria-label="Close sidebar"
          >
            <X size={20} />
          </button>
        </div>
        <Button variant="primary" fullWidth onClick={handleNewChat}>
          <Plus size={16} />
          New Chat
        </Button>
      </div>

      <div className={styles.convSection}>
        <div className={styles.convHeaderRow}>
          <h3 className={styles.convHeader}>Conversations</h3>
          {!isAnonymous && conversations.length > 0 && (
            <div className={styles.settingsMenuContainer} ref={settingsRef}>
              <button
                type="button"
                className={styles.settingsBtn}
                onClick={() => setIsSettingsOpen((prev) => !prev)}
                title="Conversation Settings"
                aria-label="Conversation Settings"
              >
                <MoreVertical size={16} />
              </button>
              {isSettingsOpen && (
                <div className={styles.settingsMenuDropdown}>
                  <button
                    type="button"
                    className={styles.dropdownItem}
                    onClick={() => {
                      setIsClearAllModalOpen(true);
                      setIsSettingsOpen(false);
                    }}
                  >
                    <Trash2 size={14} style={{ marginRight: '8px' }} />
                    Clear All Chats
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        <div className={styles.convList}>
          {isAnonymous ? (
            <div className={styles.anonBanner}>
              <div className={styles.bannerTitle}>
                <Sparkles size={14} />
                <span>Save History</span>
              </div>
              <p className={styles.bannerText}>
                Sign in with Google to save your chat logs and sync queries across tabs.
              </p>
            </div>
          ) : isLoadingConversations ? (
            <>
              <div className={styles.skeletonItem} />
              <div className={styles.skeletonItem} />
              <div className={styles.skeletonItem} />
            </>
          ) : conversations.length === 0 ? (
            <p className={styles.convPlaceholder}>No conversations yet</p>
          ) : (
            conversations.map((conv) => {
              const isActive = activeConversationId === conv.id;
              const isEditing = editingConvId === conv.id;

              return (
                <div
                  key={conv.id}
                  className={`${styles.convItem} ${isActive ? styles.convItemActive : ''}`}
                  onClick={() => {
                    if (!isEditing) {
                      navigate(`/app/${conv.id}`);
                      onClose();
                    }
                  }}
                >
                  <div className={styles.convItemTitleRow}>
                    {isEditing ? (
                      <input
                        ref={inputRef}
                        type="text"
                        className={styles.convInput}
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onBlur={() => handleRenameSubmit(conv.id)}
                        onKeyDown={(e) => handleRenameKeyDown(e, conv.id)}
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <>
                        <span className={styles.convItemTitle} title={conv.title}>
                          {conv.title}
                        </span>
                        <div style={{ display: 'flex', gap: '4px' }}>
                          <button
                            type="button"
                            className={styles.convEditBtn}
                            onClick={(e) => startRename(conv, e)}
                            title="Rename Conversation"
                          >
                            <Pencil size={12} />
                          </button>
                          <button
                            type="button"
                            className={styles.convDeleteBtn}
                            onClick={(e) => openDeleteModal(conv.id, e)}
                            title="Delete Conversation"
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                  <span className={styles.convMeta}>{formatRelativeTime(conv.updatedAt)}</span>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Uploaded Documents List */}
      <div className={styles.docSection}>
        <h3 className={styles.convHeader}>Documents</h3>
        <div className={styles.docList}>
          {uploadedDocuments.length === 0 ? (
            <p className={styles.convPlaceholder}>No documents uploaded</p>
          ) : (
            uploadedDocuments.map((doc) => {
              const isActive = activeDocument?.document_id === doc.document_id;
              return (
                <div
                  key={doc.document_id}
                  className={`${styles.docItem} ${isActive ? styles.docItemActive : ''}`}
                  onClick={() => {
                    setActiveDocument(doc);
                    onClose();
                  }}
                >
                  <File className={styles.docIcon} size={16} />
                  <div className={styles.docContent}>
                    <span className={styles.docTitle} title={doc.filename}>
                      {doc.filename}
                    </span>
                    <span className={styles.docMeta}>
                      {doc.page_count} pages • {doc.upload_date}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Modals Section */}
      <ConfirmModal
        isOpen={isDeleteModalOpen}
        onClose={() => {
          setIsDeleteModalOpen(false);
          setSelectedConvId(null);
        }}
        onConfirm={handleDeleteConfirm}
        title="Delete Conversation"
        message="Delete this conversation? This can't be undone."
        confirmText="Delete"
        isDestructive={true}
        isLoading={isDeleteLoading}
      />

      <Modal
        isOpen={isClearAllModalOpen}
        onClose={() => {
          setIsClearAllModalOpen(false);
          setConfirmClearText('');
        }}
        title="Clear All Conversations"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setIsClearAllModalOpen(false);
                setConfirmClearText('');
              }}
              disabled={isClearAllLoading}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={handleClearAllConfirm}
              disabled={confirmClearText.toLowerCase() !== 'delete'}
              isLoading={isClearAllLoading}
            >
              Clear All
            </Button>
          </>
        }
        maxWidth="440px"
      >
        <div style={{ textAlign: 'left' }}>
          <p
            style={{
              color: 'var(--color-text-secondary)',
              fontSize: 'var(--font-size-sm)',
              margin: '0 0 var(--space-sm) 0',
              lineHeight: '1.5',
            }}
          >
            This action will permanently delete all your conversation history. This cannot be
            undone. Please type <strong>delete</strong> below to confirm.
          </p>
          <input
            type="text"
            className={styles.confirmInput}
            value={confirmClearText}
            onChange={(e) => setConfirmClearText(e.target.value)}
            placeholder="Type 'delete' to confirm"
            disabled={isClearAllLoading}
          />
        </div>
      </Modal>
    </aside>
  );
}

Sidebar.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
};
