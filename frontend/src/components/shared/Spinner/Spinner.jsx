import PropTypes from 'prop-types';
import styles from './Spinner.module.css';

export default function Spinner({ size = 'md', className = '' }) {
  const spinnerClass = `${styles.spinner} ${styles[size]} ${className}`;
  return <span className={spinnerClass} role="status" aria-label="Loading" />;
}

Spinner.propTypes = {
  size: PropTypes.oneOf(['sm', 'md', 'lg']),
  className: PropTypes.string,
};
