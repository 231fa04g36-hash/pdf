import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import styles from './LoginPage.module.css';

export default function LoginPage() {
  const { user, signInWithGoogle, signOut, isLoading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (user) {
      navigate('/app', { replace: true });
    }
  }, [user, navigate]);

  const handleDemoLogin = () => {
    signInWithGoogle();
  };

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <h1 className={styles.title}>PDF Chatbot Login</h1>
        <p className={styles.subtitle}>Sign in to start chatting with your PDFs</p>

        {user ? (
          <div className={styles.loggedIn}>
            <p>
              Signed in as: <strong>{user.email}</strong>
            </p>
            <button type="button" className={styles.button} onClick={signOut}>
              Sign Out
            </button>
          </div>
        ) : (
          <button
            type="button"
            className={styles.button}
            onClick={handleDemoLogin}
            disabled={isLoading}
          >
            {isLoading ? 'Signing in...' : 'Sign In with Google'}
          </button>
        )}
      </div>
    </div>
  );
}
