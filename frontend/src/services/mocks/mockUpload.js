export const mockUpload = async (file, onProgress, errorType = null) => {
  const total = 100;
  let loaded = 0;

  return new Promise((resolve, reject) => {
    const interval = setInterval(() => {
      loaded += 10;
      if (onProgress) {
        onProgress({ loaded, total });
      }

      if (loaded >= total) {
        clearInterval(interval);

        // Check simulated errors
        if (errorType === 'corrupted') {
          reject(
            new Error(
              'Corrupted PDF file: The uploaded document has missing metadata or syntax errors'
            )
          );
        } else if (errorType === 'too_large') {
          reject(new Error('File limit exceeded: PDF file size exceeds the maximum limit of 10MB'));
        } else if (errorType === 'network') {
          reject(new Error('Connection failure: Network request timed out. Please try again'));
        } else {
          // Resolve mock success
          resolve({
            document_id: 'mock-doc-' + Math.random().toString(36).substring(2, 11),
            filename: file.name,
            page_count: 12,
            ocr_triggered: file.name.toLowerCase().includes('ocr'),
            upload_date: new Date().toLocaleDateString(),
          });
        }
      }
    }, 150);
  });
};
