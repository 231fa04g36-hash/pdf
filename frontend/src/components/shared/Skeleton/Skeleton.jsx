import PropTypes from 'prop-types';
import styles from './Skeleton.module.css';

export default function Skeleton({
  variant = 'block',
  width = '100%',
  height = '20px',
  rows = 1,
  className = '',
  ...props
}) {
  if (variant === 'document') {
    return (
      <div className={`${styles.documentPage} ${className}`} {...props}>
        <div className={styles.documentHeader}>
          <span className={`${styles.skeleton} ${styles.documentTitle}`} />
          <span className={`${styles.skeleton} ${styles.documentSubtitle}`} />
        </div>
        <div className={styles.documentBody}>
          <span className={`${styles.skeleton} ${styles.documentLine}`} />
          <span className={`${styles.skeleton} ${styles.documentLine}`} />
          <span className={`${styles.skeleton} ${styles.documentLine}`} />
          <span className={`${styles.skeleton} ${styles.documentLine}`} />
          <span className={`${styles.skeleton} ${styles.documentLine}`} />
          <span className={`${styles.skeleton} ${styles.documentLine}`} />
        </div>
      </div>
    );
  }

  if (variant === 'text' && rows > 1) {
    return (
      <div className={className} {...props}>
        {Array.from({ length: rows }).map((_, index) => {
          const isLast = index === rows - 1;
          return (
            <span
              key={index}
              className={`${styles.skeleton} ${styles.text} ${isLast ? styles.textLastLine : ''}`}
              aria-hidden="true"
            />
          );
        })}
      </div>
    );
  }

  const skeletonClass = [
    styles.skeleton,
    variant === 'circle' ? styles.circle : '',
    variant === 'text' ? styles.text : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  const inlineStyles = {
    width: variant === 'text' ? undefined : width,
    height: variant === 'text' ? undefined : height,
  };

  return <span className={skeletonClass} style={inlineStyles} aria-hidden="true" {...props} />;
}

Skeleton.propTypes = {
  variant: PropTypes.oneOf(['block', 'circle', 'text', 'document']),
  width: PropTypes.string,
  height: PropTypes.string,
  rows: PropTypes.number,
  className: PropTypes.string,
};
