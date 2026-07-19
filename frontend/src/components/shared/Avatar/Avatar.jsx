import { useState } from 'react';
import PropTypes from 'prop-types';
import styles from './Avatar.module.css';

export default function Avatar({
  src = '',
  name = '',
  size = 'md',
  variant = 'user',
  className = '',
}) {
  const [imageError, setImageError] = useState(false);

  const getInitials = (fullName) => {
    if (!fullName) return '';
    const parts = fullName.split(' ').filter(Boolean);
    if (parts.length === 0) return '';
    if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
    return (parts[0][0] + parts[1][0]).toUpperCase();
  };

  const avatarClass = [styles.avatar, styles[size], styles[variant], className]
    .filter(Boolean)
    .join(' ');

  const showImage = src && !imageError;

  return (
    <div className={avatarClass}>
      {showImage ? (
        <img src={src} alt={name} className={styles.img} onError={() => setImageError(true)} />
      ) : (
        <span>{getInitials(name) || (variant === 'assistant' ? 'AI' : 'U')}</span>
      )}
    </div>
  );
}

Avatar.propTypes = {
  src: PropTypes.string,
  name: PropTypes.string,
  size: PropTypes.oneOf(['sm', 'md', 'lg']),
  variant: PropTypes.oneOf(['user', 'assistant']),
  className: PropTypes.string,
};
