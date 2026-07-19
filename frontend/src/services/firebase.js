import { initializeApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider, signInWithPopup, signOut } from 'firebase/auth';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

// OLD: Simple initialization of firebase app and auth that crashes if config is dummy/invalid.
// Used to directly initialize and export firebase auth variables without validation.
// if (import.meta.env.VITE_USE_MOCK_API !== 'true') {
//   app = initializeApp(firebaseConfig);
//   auth = getAuth(app);
// }
// export { auth, googleProvider, signInWithPopup, signOut };

// NEW: Helper function to create a mock auth object for local dev when Firebase keys are not valid
const createMockAuth = () => {
  let currentUser = null;
  const listeners = [];

  const onAuthStateChanged = (callback) => {
    listeners.push(callback);
    // Instantly notify listener of current user state
    setTimeout(() => callback(currentUser), 0);
    return () => {
      const idx = listeners.indexOf(callback);
      if (idx !== -1) listeners.splice(idx, 1);
    };
  };

  const triggerStateChange = () => {
    listeners.forEach((cb) => cb(currentUser));
  };

  return {
    get currentUser() {
      return currentUser;
    },
    onAuthStateChanged,
    signInFakeUser: () => {
      currentUser = {
        uid: 'firebase-test-user-123',
        displayName: 'Dev User',
        email: 'developer@pdfchatbot.com',
        photoURL: null,
        getIdToken: async () => 'mock-token-for-dev',
      };
      triggerStateChange();
      return currentUser;
    },
    signOutFakeUser: () => {
      currentUser = null;
      triggerStateChange();
    },
  };
};

let app;
let auth;
const googleProvider = new GoogleAuthProvider();

const isDummyConfig = !firebaseConfig.apiKey || firebaseConfig.apiKey.startsWith('your-');

// Check if we should initialize real Firebase client or fall back to mock auth
if (import.meta.env.VITE_USE_MOCK_API !== 'true' && !isDummyConfig) {
  try {
    app = initializeApp(firebaseConfig);
    auth = getAuth(app);
  } catch (err) {
    console.warn('Failed to initialize real Firebase, falling back to mock auth mode:', err);
    auth = createMockAuth();
  }
} else {
  // If mock API is enabled or config is dummy, initialize mock auth state
  auth = createMockAuth();
}

export { auth, googleProvider, signInWithPopup, signOut };
