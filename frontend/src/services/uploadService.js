import api from './api';
import { isMockEnabled } from './mocks/mockConfig';
import { mockUpload } from './mocks/mockUpload';

export const uploadPDF = async (file, onProgress, errorType = null) => {
  if (isMockEnabled()) {
    return mockUpload(file, onProgress, errorType);
  }

  const formData = new FormData();
  formData.append('file', file);

  // OLD: Call to obsolete upload endpoint path /upload
  // return api.post('/upload', formData, {

  // NEW: Updated to target document upload endpoint path /documents/upload as defined in backend routers
  const response = await api.post('/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 300000, // 5 minutes override for uploading & processing large PDFs
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        onProgress({
          loaded: progressEvent.loaded,
          total: progressEvent.total,
        });
      }
    },
  });
  return response.data;
};
