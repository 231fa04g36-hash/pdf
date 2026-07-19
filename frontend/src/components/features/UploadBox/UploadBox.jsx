import { useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { useMutation } from '@tanstack/react-query';
import { UploadCloud, CheckCircle, AlertTriangle, Info, ArrowRight, RotateCcw } from 'lucide-react';
import { useConversationStore } from '../../../stores/conversationStore';
import { uploadPDF } from '../../../services/uploadService';
import { showSuccessToast, showErrorToast } from '../../../utils/toast';
import Skeleton from '../../shared/Skeleton/Skeleton';
import Button from '../../shared/Button/Button';
import styles from './UploadBox.module.css';

export default function UploadBox() {
  const { addUploadedDocument, setActiveDocument } = useConversationStore();

  const [progress, setProgress] = useState(0);
  const [loadedBytes, setLoadedBytes] = useState(0);
  const [totalBytes, setTotalBytes] = useState(0);
  const [uploadStatus, setUploadStatus] = useState('idle'); // idle, uploading, success, error
  const [resultData, setResultData] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [devErrorType, setDevErrorType] = useState('none');
  const [currentFile, setCurrentFile] = useState(null);

  const isMock = import.meta.env.VITE_USE_MOCK_API === 'true';

  const mutation = useMutation({
    mutationFn: async (file) => {
      setUploadStatus('uploading');
      setProgress(0);
      setCurrentFile(file);
      return uploadPDF(
        file,
        ({ loaded, total }) => {
          setLoadedBytes(loaded);
          setTotalBytes(total);
          const percent = Math.round((loaded * 100) / total);
          setProgress(percent);
        },
        devErrorType !== 'none' ? devErrorType : null
      );
    },
    onSuccess: (data) => {
      setUploadStatus('success');
      setResultData(data);
      showSuccessToast('PDF uploaded successfully!');
      addUploadedDocument(data);
    },
    onError: (err) => {
      setUploadStatus('error');
      setErrorMessage(err.message || 'An unexpected error occurred');

      let toastMessage = 'Upload failed: ';
      if (err.message.includes('Corrupted')) {
        toastMessage += 'The PDF appears corrupted or unreadable.';
      } else if (err.message.includes('limit')) {
        toastMessage += 'File is too large (maximum limit is 10MB).';
      } else if (err.message.includes('Connection') || err.message.includes('timed out')) {
        toastMessage += 'Network connection timed out. Please check your network and retry.';
      } else {
        toastMessage += err.message || 'An unexpected error occurred.';
      }
      showErrorToast(toastMessage);
    },
  });

  const onDrop = (acceptedFiles, fileRejections) => {
    // Immediate validation of react-dropzone rejects
    if (fileRejections && fileRejections.length > 0) {
      const rejection = fileRejections[0];
      const error = rejection.errors[0];
      if (error.code === 'file-too-large') {
        showErrorToast('File too large: Maximum limit is 10MB.');
        return;
      }
      if (error.code === 'file-invalid-type') {
        showErrorToast('Invalid file type: Only PDF documents are supported.');
        return;
      }
      showErrorToast(`Validation failed: ${error.message}`);
      return;
    }

    if (acceptedFiles.length === 0) return;
    const file = acceptedFiles[0];

    // OLD: MIME type check relied solely on react-dropzone's accept prop, 
    // which filters what's selectable in some browsers but can still be 
    // bypassed via drag-and-drop of a renamed non-PDF file in others — 
    // replaced/extended below with an explicit file.type and extension check 
    // as a second layer, alongside a new empty-file validation.
    // if (file.type !== 'application/pdf') {
    //   showErrorToast('Invalid file type: Only PDF documents are supported.');
    //   return;
    // }
    // if (file.size > 10 * 1024 * 1024) {
    //   showErrorToast('File too large: Maximum limit is 10MB.');
    //   return;
    // }

    const fileExtension = file.name ? file.name.split('.').pop().toLowerCase() : '';
    if (file.type !== 'application/pdf' && fileExtension !== 'pdf') {
      showErrorToast('Invalid file type: Only PDF documents are supported.');
      return;
    }
    if (file.size === 0) {
      showErrorToast('This file appears to be empty.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      showErrorToast('File too large: Maximum limit is 10MB.');
      return;
    }

    mutation.mutate(file);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
    },
    maxSize: 10 * 1024 * 1024,
    multiple: false,
  });

  const handleRetry = () => {
    if (currentFile) {
      mutation.mutate(currentFile);
    } else {
      setUploadStatus('idle');
    }
  };

  const handleStartChatting = () => {
    if (resultData) {
      setActiveDocument(resultData);
    }
  };

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = 2;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  };

  return (
    <div className={styles.container}>
      {uploadStatus === 'idle' && (
        <>
          <div
            {...getRootProps()}
            className={`${styles.dropzone} ${isDragActive ? styles.dragActive : ''}`}
          >
            <input {...getInputProps()} />
            <UploadCloud className={styles.icon} size={48} />
            <div>
              <p className={styles.text}>Drag & drop your PDF here, or click to browse</p>
              <p className={styles.subtext}>Supports only PDF files up to 10MB</p>
            </div>
          </div>

          {/* Dev Simulated outcomes dropdown in Mock mode */}
          {isMock && (
            <div className={styles.devTools}>
              <span style={{ fontWeight: 600 }}>[Dev Option] Simulated Mock Outcome:</span>
              <select
                className={styles.devSelect}
                value={devErrorType}
                onChange={(e) => setDevErrorType(e.target.value)}
              >
                <option value="none">Success (standard 12-page PDF)</option>
                <option value="corrupted">Error: Corrupted/Unreadable PDF</option>
                <option value="too_large">Error: File Too Large (max limit)</option>
                <option value="network">Error: Network Timeout</option>
              </select>
              <span style={{ fontSize: '11px', opacity: 0.8 }}>
                * Hint: Rename files to contain &quot;ocr&quot; (e.g. ocr_report.pdf) to test OCR
                notes.
              </span>
            </div>
          )}
        </>
      )}

      {uploadStatus === 'uploading' && (
        <div className={styles.box}>
          <div className={styles.progressHeader}>
            <span>{progress < 100 ? 'Uploading document...' : 'Processing document...'}</span>
            <span>{progress}%</span>
          </div>
          <div className={styles.progressBarContainer}>
            <div className={styles.progressBar} style={{ width: `${progress}%` }} />
          </div>
          <div className={styles.progressDetails}>
            {progress < 100
              ? `Transferred ${formatBytes(loadedBytes)} of ${formatBytes(totalBytes)}`
              : (
                <div className={styles.processingWrapper}>
                  <span>Analyzing layout and extracting pages...</span>
                  {/* OLD: Showed a generic Spinner or bare layout during server processing wait — 
                  // replaced below with a shimmer card placeholder representing where the 
                  // filename/page-count confirmation card will appear.
                  // <Spinner /> [old loading spinner placeholder] */}
                  <div className={styles.processingSkeleton}>
                    <Skeleton variant="block" height="20px" width="80%" />
                    <Skeleton variant="block" height="16px" width="60%" style={{ marginTop: '8px' }} />
                  </div>
                </div>
              )}
          </div>
        </div>
      )}

      {uploadStatus === 'success' && resultData && (
        <div className={`${styles.box} ${styles.successCard}`}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <CheckCircle className={styles.successIcon} size={32} />
            <div>
              <h3 className={styles.successTitle}>Processing complete ✓</h3>
              <p className={styles.subtext}>Your document is ready for queries</p>
            </div>
          </div>

          <div className={styles.docInfo}>
            <div>
              <strong>Filename:</strong> {resultData.filename}
            </div>
            <div>
              <strong>Page Count:</strong> {resultData.page_count} pages
            </div>
            <div>
              <strong>Uploaded on:</strong> {resultData.upload_date}
            </div>
          </div>

          {resultData.ocr_triggered && (
            <div className={styles.ocrNote}>
              <Info className={styles.ocrIcon} size={16} />
              <span>This document required OCR — processing may take longer.</span>
            </div>
          )}

          <Button variant="primary" onClick={handleStartChatting} fullWidth>
            <span>Start Chatting</span>
            <ArrowRight size={16} style={{ marginLeft: '6px' }} />
          </Button>
        </div>
      )}

      {uploadStatus === 'error' && (
        <div className={`${styles.box} ${styles.errorCard}`}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <AlertTriangle className={styles.errorIcon} size={32} />
            <div>
              <h3 className={styles.errorTitle}>Upload failed</h3>
              <p className={styles.subtext}>We encountered an issue reading the file</p>
            </div>
          </div>

          <div
            style={{
              fontSize: 'var(--font-size-sm)',
              color: 'var(--color-text-primary)',
              textAlign: 'left',
            }}
          >
            <strong>Reason:</strong> {errorMessage}
          </div>

          <div style={{ display: 'flex', gap: '12px', marginTop: '4px' }}>
            <Button variant="secondary" onClick={() => setUploadStatus('idle')} fullWidth>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleRetry} fullWidth>
              <RotateCcw size={16} style={{ marginRight: '6px' }} />
              Retry
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
