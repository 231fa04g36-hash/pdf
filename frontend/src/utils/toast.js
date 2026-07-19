import { toast } from 'react-hot-toast';

export const showSuccessToast = (message) => {
  toast.success(message, {
    id: message, // Prevent duplicate active toasts for same message
  });
};

export const showErrorToast = (message) => {
  toast.error(message, {
    id: message, // Prevent duplicate active toasts for same message
  });
};
