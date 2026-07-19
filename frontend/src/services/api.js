// OLD: Simple axios client setup without request interceptors or token/session headers support.
// import axios from 'axios';
// import { showErrorToast } from '../utils/toast';
//
// const api = axios.create({
//   baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
//   timeout: 15000,
//   headers: {
//     'Content-Type': 'application/json',
//   },
// });

import axios from 'axios';
import { showErrorToast } from '../utils/toast';
import { auth } from './firebase';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Helper function to extract cookie values (for guest session tracking)
const getCookie = (name) => {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
};

// Request interceptor to attach Authorization token and X-Session-Id to all outgoing Axios requests
api.interceptors.request.use(
  async (config) => {
    // 1. Attach guest session ID if present in cookies
    const sId = getCookie('session_id');
    if (sId) {
      config.headers['X-Session-Id'] = sId;
    }

    // 2. Attach Authorization Bearer token if user is authenticated (supports mock tokens as well)
    if (auth && auth.currentUser) {
      try {
        const token = await auth.currentUser.getIdToken();
        config.headers['Authorization'] = `Bearer ${token}`;
      } catch (err) {
        console.error('Error retrieving Firebase ID token for Axios request:', err);
      }
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to format backend responses consistently according to guidelines
api.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error) => {
    const status = error.response?.status;
    let message = 'An unexpected error occurred';

    if (status === 401) {
      message = 'Your session has expired. Redirecting to login...';
      showErrorToast(message);
      // Wait a moment so user can read the toast before redirect
      setTimeout(() => {
        window.location.href = '/';
      }, 1500);
    } else if (status === 403) {
      message = 'Access denied. Redirecting to app...';
      showErrorToast(message);
      setTimeout(() => {
        window.location.href = '/app';
      }, 1500);
    } else if (status === 500) {
      message = 'A generic server error occurred. Please try again later.';
      // Log/rethrow only, let caller component show the specific error toast
      // showErrorToast(message);
    } else {
      // General error status fallback
      message =
        error.response?.data?.message || error.message || 'An unexpected network error occurred.';
      // Log/rethrow only, let caller component show the specific error toast
      // showErrorToast(message);
    }

    const errorResponse = {
      success: false,
      message,
      data: error.response?.data?.data || null,
    };
    return Promise.reject(errorResponse);
  }
);

export default api;
