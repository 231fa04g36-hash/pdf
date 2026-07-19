import api from './api';
import { auth, googleProvider, signInWithPopup, signOut } from './firebase';
import { isMockEnabled, delay } from './mocks/mockConfig';
import { mockUser, mockLinkSession } from './mocks/mockAuth';

// OLD: Sign in function that triggers real Firebase sign-in popup.
// Used for authenticating users via Google and Firebase Auth.
// export const signInWithGoogle = async (triggerError = false) => {
//   if (isMockEnabled()) {
//     await delay(500);
//     if (triggerError) {
//       throw new Error('Firebase Auth error: Popup blocked by browser settings');
//     }
//     return mockUser;
//   }
//
//   // Real Firebase sign-in with popup
//   const result = await signInWithPopup(auth, googleProvider);
//   return result.user;
// };

// NEW: Updated sign-in function that uses mock fallback if Firebase keys are not valid
export const signInWithGoogle = async (triggerError = false) => {
  if (isMockEnabled()) {
    await delay(500);
    if (triggerError) {
      throw new Error('Firebase Auth error: Popup blocked by browser settings');
    }
    return mockUser;
  }

  // Fallback to local fake user sign in if mock auth mode is enabled
  if (auth && typeof auth.signInFakeUser === 'function') {
    await delay(500);
    return auth.signInFakeUser();
  }

  // Real Firebase sign-in with popup
  const result = await signInWithPopup(auth, googleProvider);
  return result.user;
};

// OLD: Sign out function that signs the user out of Firebase.
// Used to clear the authenticated user's session.
// export const signOutUser = async () => {
//   if (isMockEnabled()) {
//     await delay(200);
//     return;
//   }
//
//   await signOut(auth);
// };

// NEW: Updated sign-out function that handles mock fallback sign-out
export const signOutUser = async () => {
  if (isMockEnabled()) {
    await delay(200);
    return;
  }

  // Fallback to local fake user sign out if mock auth mode is enabled
  if (auth && typeof auth.signOutFakeUser === 'function') {
    auth.signOutFakeUser();
    return;
  }

  await signOut(auth);
};

export const linkSession = async (sessionId, googleUid) => {
  if (isMockEnabled()) {
    await delay(200);
    return mockLinkSession();
  }

  return api.post('/auth/link-session', {
    session_id: sessionId,
    google_uid: googleUid,
  });
};
