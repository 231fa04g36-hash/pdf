import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import PropTypes from 'prop-types';
import { Menu, FileText, ShieldAlert, File, Sun, Moon } from 'lucide-react';
import { useAuth } from '../../../contexts/AuthContext';
import { useTheme } from '../../../contexts/ThemeContext';
import { useConversationStore } from '../../../stores/conversationStore';
import Avatar from '../../shared/Avatar/Avatar';
import Button from '../../shared/Button/Button';
import styles from './TopBar.module.css';

// Google Flat Colored G Icon SVG
function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18">
      <path
        fill="#EA4335"
        d="M20.64 12.2c0-.7-.06-1.36-.18-2H12v3.8h4.84c-.2 1.1-.84 2.02-1.8 2.66v2.22h2.9c1.7-1.57 2.7-3.87 2.7-6.68z"
      />
      <path
        fill="#34A853"
        d="M12 21c2.43 0 4.47-.8 5.96-2.22l-2.9-2.22c-.8.54-1.84.88-3.06.88-2.36 0-4.36-1.58-5.07-3.72H3.9v2.28C5.38 18.92 8.44 21 12 21z"
      />
      <path
        fill="#FBBC05"
        d="M6.93 13.72c-.18-.54-.28-1.12-.28-1.72s.1-1.18.28-1.72V8.02H3.9A8.96 8.96 0 003 12c0 1.45.35 2.82.97 4.02l3.06-2.3z"
      />
      <path
        fill="#4285F4"
        d="M12 6.12c1.32 0 2.5.45 3.44 1.34l2.58-2.58C16.46 3.32 14.42 2.5 12 2.5c-3.56 0-6.62 2.08-8.1 5.52l3.06 2.28c.7-2.14 2.7-3.72 5.07-3.72z"
      />
    </svg>
  );
}

export default function TopBar({ onToggleSidebar }) {
  const { user, isAnonymous, isLoading, signInWithGoogle, signOut } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { activeDocument } = useConversationStore();
  const location = useLocation();

  // Checks if mockError=true query param is present
  const searchParams = new URLSearchParams(location.search);
  const queryMockError = searchParams.get('mockError') === 'true';

  // Local state to simulate error via UI trigger in mock mode
  const [forceError, setForceError] = useState(false);

  const handleSignIn = async () => {
    try {
      await signInWithGoogle(queryMockError || forceError);
    } catch {
      // Errors are caught and toasted by the AuthContext provider
    }
  };

  const isMock = import.meta.env.VITE_USE_MOCK_API === 'true';

  return (
    <header className={styles.topBar}>
      <div className={styles.left}>
        <button
          type="button"
          className={styles.menuButton}
          onClick={onToggleSidebar}
          aria-label="Toggle sidebar menu"
        >
          <Menu size={24} />
        </button>
        <a href="/app" className={styles.logoText}>
          <FileText className={styles.logoIcon} size={24} />
          <span>PDF Chatbot</span>
        </a>
      </div>

      <div className={styles.center}>
        {/* Document Status Indicator */}
        <div
          className={`${styles.docIndicator} ${activeDocument ? styles.docIndicatorActive : ''}`}
          title={activeDocument ? `Active: ${activeDocument.filename}` : 'Active Document Context'}
        >
          <File size={16} />
          <span>
            {activeDocument
              ? `${activeDocument.filename} (${activeDocument.page_count} pages)`
              : 'No Document Selected'}
          </span>
        </div>
      </div>

      <div className={styles.right}>
        {/* Temporary Developer Diagnostic Trigger */}
        {isMock && isAnonymous && (
          <button
            type="button"
            className={styles.devDiagnosticBtn}
            onClick={() => setForceError(!forceError)}
            title="Toggle simulated sign-in error for pop-up blocking verification"
          >
            <ShieldAlert size={16} style={{ marginRight: '6px' }} />
            Error: {forceError ? 'ON' : 'OFF'}
          </button>
        )}

        <button
          type="button"
          className={styles.themeToggle}
          onClick={toggleTheme}
          title={theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
          aria-label="Toggle theme mode"
        >
          {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
        </button>

        {isAnonymous ? (
          <button
            type="button"
            className={styles.googleBtn}
            onClick={handleSignIn}
            disabled={isLoading}
          >
            <GoogleIcon />
            <span>{isLoading ? 'Signing in...' : 'Sign in with Google'}</span>
          </button>
        ) : (
          <div className={styles.profile}>
            <div className={styles.userInfo}>
              <span className={styles.userName}>{user.displayName || 'Google User'}</span>
              <span className={styles.userEmail}>{user.email}</span>
            </div>
            <Avatar src={user.photoURL} name={user.displayName || 'U'} size="sm" />
            <Button variant="ghost" size="sm" onClick={signOut} disabled={isLoading}>
              Sign Out
            </Button>
          </div>
        )}
      </div>
    </header>
  );
}

TopBar.propTypes = {
  onToggleSidebar: PropTypes.func.isRequired,
};
