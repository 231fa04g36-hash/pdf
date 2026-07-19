import { useState, useEffect, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import PropTypes from 'prop-types';
import { X, ChevronLeft, ChevronRight, AlertTriangle } from 'lucide-react';
import { useConversationStore } from '../../../stores/conversationStore';
import Spinner from '../../shared/Spinner/Spinner';
import Skeleton from '../../shared/Skeleton/Skeleton';
import Button from '../../shared/Button/Button';
import styles from './PdfPageViewer.module.css';
import api from '../../../services/api';

// Vite-specific worker setup
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
pdfjs.GlobalWorkerOptions.workerSrc = workerSrc;

import 'react-pdf/dist/Page/TextLayer.css';
import 'react-pdf/dist/Page/AnnotationLayer.css';

const parsePageNumber = (page) => {
  if (typeof page === 'number') {
    return page;
  }
  if (typeof page === 'string') {
    const match = page.match(/(\d+)/);
    if (match) {
      return parseInt(match[1], 10);
    }
  }
  return 1;
};

export default function PdfPageViewer({ citation, onClose }) {
  const { activeDocument } = useConversationStore();
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(() => citation?.page ? parsePageNumber(citation.page) : 1);
  const [loadError, setLoadError] = useState(null);
  const [fileUrl, setFileUrl] = useState(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [rendered, setRendered] = useState(false);

  const containerRef = useRef(null);

  // Close the viewer on Escape key press
  useEffect(() => {
    if (citation?.page) {
      setPageNumber(parsePageNumber(citation.page));
    }
  }, [citation?.page]);

  // Scroll to the highlighted passage once rendering is complete
  useEffect(() => {
    if (rendered && citation?.snippet) {
      const highlightedEl = containerRef.current?.querySelector('.highlight');
      if (highlightedEl) {
        highlightedEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      setRendered(false);
    }
  }, [rendered, pageNumber, citation]);

  // Close the viewer on Escape key press
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const isMock = import.meta.env.VITE_USE_MOCK_API === 'true';

  // Fetch the PDF file as a blob from backend with authorization headers
  useEffect(() => {
    if (isMock) {
      setFileUrl('/sample.pdf');
      return;
    }
    if (!activeDocument?.document_id) return;

    let isMounted = true;
    let currentUrl = null;
    setIsDownloading(true);
    setLoadError(null);

    api.get(`/documents/${activeDocument.document_id}/file`, { responseType: 'blob' })
      .then((blob) => {
        if (isMounted) {
          currentUrl = URL.createObjectURL(blob);
          setFileUrl(currentUrl);
          setIsDownloading(false);
        }
      })
      .catch((err) => {
        console.error('Error downloading PDF:', err);
        if (isMounted) {
          setLoadError(err.message || 'Failed to download PDF document from server.');
          setIsDownloading(false);
        }
      });

    return () => {
      isMounted = false;
      if (currentUrl) {
        URL.revokeObjectURL(currentUrl);
      }
    };
  }, [activeDocument?.document_id, isMock]);

  const onDocumentLoadSuccess = ({ numPages: loadedPages }) => {
    setNumPages(loadedPages);
    setLoadError(null);
    const parsedPage = citation?.page ? parsePageNumber(citation.page) : 1;
    if (parsedPage > loadedPages) {
      setPageNumber(1);
    } else {
      setPageNumber(parsedPage);
    }
  };

  const onDocumentLoadError = (err) => {
    console.error(err);
    setLoadError(err.message || 'Failed to load PDF document.');
  };

  const changePage = (offset) => {
    setPageNumber((prevPageNumber) => {
      const nextPage = prevPageNumber + offset;
      return Math.min(Math.max(1, nextPage), numPages || 1);
    });
  };

  const highlightPattern = (text, pattern) => {
    if (!pattern || !pattern.trim()) return text;

    const cleanText = text.trim().replace(/\s+/g, ' ').toLowerCase();
    const cleanPattern = pattern.trim().replace(/\s+/g, ' ').toLowerCase();

    // 1. Try exact match first
    const cleanEscapedPattern = pattern
      .replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&')
      .replace(/\s+/g, '\\s+');
    const exactRegex = new RegExp(`(${cleanEscapedPattern})`, 'gi');
    if (exactRegex.test(text)) {
      return text.replace(exactRegex, (match) => `<mark class="highlight">${match}</mark>`);
    }

    // 2. If the entire text item is a substring of the cited passage (minimum 5 chars)
    if (cleanText.length >= 5 && cleanPattern.includes(cleanText)) {
      return `<mark class="highlight">${text}</mark>`;
    }

    // 3. Fallback: break pattern into 4-word phrases and match them
    const words = pattern.split(/\s+/).filter(w => w.length > 0);
    const phrases = [];
    const windowSize = 4;
    for (let i = 0; i <= words.length - windowSize; i++) {
      phrases.push(words.slice(i, i + windowSize).join(' '));
    }

    if (phrases.length === 0) {
      phrases.push(pattern);
    }

    // Filter out phrases that contain only tiny words (to prevent false positives)
    // A phrase must have at least one word of length >= 4
    const validPhrases = phrases.filter(phrase => {
      return phrase.split(/\s+/).some(w => w.replace(/[^a-zA-Z0-9]/g, '').length >= 4);
    });

    if (validPhrases.length === 0) return text;

    // Sort phrases by length descending to match longest first
    validPhrases.sort((a, b) => b.length - a.length);

    // Escape and join them as alternations
    const escapedPhrases = validPhrases.map(phrase => 
      phrase.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&').replace(/\s+/g, '\\s+')
    );

    // Create regex matching any of the 4-word phrases
    const phraseRegex = new RegExp(`(${escapedPhrases.join('|')})`, 'gi');
    
    let matched = false;
    const result = text.replace(phraseRegex, (match) => {
      matched = true;
      return `<mark class="highlight">${match}</mark>`;
    });

    return result;
  };

  const makeTextRenderer = (snippet) => {
    console.log('[Highlight Debug] Initializing makeTextRenderer for snippet:', snippet);
    return (textItem) => highlightPattern(textItem.str, snippet);
  };

  return (
    <div className={styles.container} ref={containerRef}>
      <div className={styles.header}>
        <div className={styles.headerRow}>
          <span className={styles.title}>Document Viewer</span>
          <button
            type="button"
            className={styles.closeBtn}
            onClick={onClose}
            aria-label="Close viewer"
          >
            <X size={20} />
          </button>
        </div>

        {citation?.snippet && (
          <div className={styles.snippetAlert}>
            <span className={styles.snippetTitle}>Cited Passage:</span>
            <span className={styles.snippetText}>&ldquo;{citation.snippet}&rdquo;</span>
          </div>
        )}
      </div>

      <div className={styles.viewerWorkspace}>
        {isDownloading ? (
          // OLD: showed a generic Spinner + "Loading..." text while a PDF page 
          // rendered in the citation panel — replaced below with a Skeleton 
          // component that mimics the page's expected layout for a more premium 
          // loading feel.
          // <div className={styles.loadingOverlay}>
          //   <Spinner size="md" />
          //   <span className={styles.pageDetails}>Downloading PDF file...</span>
          // </div>
          <div className={styles.skeletonContainer}>
            <Skeleton variant="document" height="100%" />
          </div>
        ) : loadError ? (
          <div className={styles.errorOverlay}>
            <AlertTriangle className={styles.errorIcon} size={40} />
            <div className={styles.errorTitle}>Error Loading PDF</div>
            <div className={styles.errorText}>{loadError}</div>
          </div>
        ) : fileUrl ? (
          <Document
            file={fileUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading={
              // OLD: showed a generic Spinner + "Loading..." text while a PDF page 
              // rendered in the citation panel — replaced below with a Skeleton 
              // component that mimics the page's expected layout for a more premium 
              // loading feel.
              // <div className={styles.loadingOverlay}>
              //   <Spinner size="md" />
              //   <span className={styles.pageDetails}>Opening PDF file...</span>
              // </div>
              <div className={styles.skeletonContainer}>
                <Skeleton variant="document" height="100%" />
              </div>
            }
          >
            <div className={styles.canvasWrapper}>
              {/* OLD: after navigating to a citation's page, the viewer rendered the page 
              // but did not scroll to the highlighted passage — user had to manually 
              // scroll to find it. Replaced below with an auto-scroll-into-view trigger.
              // <Page
              //   key={`${pageNumber}_${citation?.snippet || ''}`}
              //   pageNumber={pageNumber}
              //   customTextRenderer={
              //     citation?.snippet ? makeTextRenderer(citation.snippet) : undefined
              //   }
              //   renderTextLayer={true}
              //   width={380}
              // /> */}

              <Page
                key={`${pageNumber}_${citation?.snippet || ''}`}
                pageNumber={pageNumber}
                customTextRenderer={
                  citation?.snippet ? makeTextRenderer(citation.snippet) : undefined
                }
                renderTextLayer={true}
                onRenderSuccess={() => setRendered(true)}
                loading={
                  // OLD: showed a generic Spinner + "Loading..." text while a PDF page 
                  // rendered in the citation panel — replaced below with a Skeleton 
                  // component that mimics the page's expected layout for a more premium 
                  // loading feel.
                  // <div className={styles.loadingOverlay}>
                  //   <Spinner size="md" />
                  //   <span>Rendering page {pageNumber}...</span>
                  // </div>
                  <div className={styles.skeletonContainer}>
                    <Skeleton variant="document" height="100%" />
                  </div>
                }
                error={
                  <div className={styles.errorOverlay}>
                    <AlertTriangle size={32} />
                    <span>Failed to render page.</span>
                  </div>
                }
                width={380}
              />
            </div>
          </Document>
        ) : null}
      </div>

      {numPages && !loadError && (
        <div className={styles.controls}>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => changePage(-1)}
            disabled={pageNumber <= 1}
          >
            <ChevronLeft size={16} />
            <span>Previous</span>
          </Button>
          <span className={styles.pageDetails}>
            Page {pageNumber} of {numPages}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => changePage(1)}
            disabled={pageNumber >= numPages}
          >
            <span>Next</span>
            <ChevronRight size={16} />
          </Button>
        </div>
      )}
    </div>
  );
}

PdfPageViewer.propTypes = {
  citation: PropTypes.shape({
    page: PropTypes.number.isRequired,
    snippet: PropTypes.string.isRequired,
  }),
  onClose: PropTypes.func.isRequired,
};
