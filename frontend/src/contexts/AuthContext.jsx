import { createContext, useContext, useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { v4 as uuidv4 } from 'uuid';
import * as authService from '../services/authService';
import { auth } from '../services/firebase';
import { showSuccessToast, showErrorToast } from '../utils/toast';

const AuthContext = createContext(null);

const getCookie = (name) => {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
};

const setSessionCookie = (name, value) => {
  document.cookie = `${name}=${value}; path=/; SameSite=Lax`;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [sessionId, setSessionId] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  // Initialize session and check existing authentication status on mount
  useEffect(() => {
    // 1. Get or generate anonymous session_id
    let sId = getCookie('session_id');
    if (!sId) {
      sId = uuidv4();
      setSessionCookie('session_id', sId);
    }
    setSessionId(sId);

    // 2. Auth state subscription (skip in mock mode)
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      setIsLoading(false);
      return;
    }

    // Real Firebase listener
    const unsubscribe = auth.onAuthStateChanged((firebaseUser) => {
      if (firebaseUser) {
        setUser({
          uid: firebaseUser.uid,
          displayName: firebaseUser.displayName,
          email: firebaseUser.email,
          photoURL: firebaseUser.photoURL,
        });
      } else {
        setUser(null);
      }
      setIsLoading(false);
    });

    return () => unsubscribe();
  }, []);

  const signInWithGoogle = async (triggerError = false) => {
    setIsLoading(true);
    try {
      const loggedUser = await authService.signInWithGoogle(triggerError);

      // Link anonymous session ID on successful sign-in
      await authService.linkSession(sessionId, loggedUser.uid);

      setUser(loggedUser);
      showSuccessToast(`Welcome back, ${loggedUser.displayName || 'User'}!`);
    } catch (error) {
      console.error(error);
      showErrorToast(error.message || 'Failed to sign in with Google');
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const signOut = async () => {
    setIsLoading(true);
    try {
      await authService.signOutUser();

      // Clear user state and generate a fresh session ID for anonymity
      setUser(null);
      const newSId = uuidv4();
      setSessionCookie('session_id', newSId);
      setSessionId(newSId);

      showSuccessToast('Signed out successfully');
    } catch (error) {
      console.error(error);
      showErrorToast('Failed to sign out');
    } finally {
      setIsLoading(false);
    }
  };

  const isAnonymous = !user;

  return (
    <AuthContext.Provider
      value={{
        user,
        sessionId,
        isAnonymous,
        isLoading,
        signInWithGoogle,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

AuthProvider.propTypes = {
  children: PropTypes.node.isRequired,
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
