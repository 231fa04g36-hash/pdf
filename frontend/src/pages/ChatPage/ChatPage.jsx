import { useConversationStore } from '../../stores/conversationStore';
import UploadBox from '../../components/features/UploadBox/UploadBox';
import ChatWindow from '../../components/features/ChatWindow/ChatWindow';
import styles from './ChatPage.module.css';

export default function ChatPage() {
  const { activeDocument } = useConversationStore();

  return (
    <div className={styles.workspace}>
      {!activeDocument ? (
        <div className={styles.inner}>
          <h1 className={styles.title}>PDF Chatbot</h1>
          <p className={styles.subtitle}>Upload a PDF file to begin asking questions</p>
          <UploadBox />
        </div>
      ) : (
        <ChatWindow />
      )}
    </div>
  );
}
