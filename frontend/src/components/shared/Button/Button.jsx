import PropTypes from 'prop-types';
import Spinner from '../Spinner/Spinner';
import styles from './Button.module.css';

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  disabled = false,
  onClick = () => {},
  type = 'button',
  ariaLabel = undefined,
  fullWidth = false,
  className = '',
  ...props
}) {
  const buttonClass = [
    styles.btn,
    styles[variant],
    styles[size],
    fullWidth ? styles.fullWidth : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <button
      type={type}
      className={buttonClass}
      onClick={onClick}
      disabled={disabled || isLoading}
      aria-label={ariaLabel}
      {...props}
    >
      {isLoading ? (
        <span className={styles.spinnerWrapper}>
          <Spinner size="sm" />
        </span>
      ) : null}
      <span className={`${styles.content} ${isLoading ? styles.hidden : ''}`}>{children}</span>
    </button>
  );
}

Button.propTypes = {
  children: PropTypes.node.isRequired,
  variant: PropTypes.oneOf(['primary', 'secondary', 'ghost', 'danger']),
  size: PropTypes.oneOf(['sm', 'md', 'lg']),
  isLoading: PropTypes.bool,
  disabled: PropTypes.bool,
  onClick: PropTypes.func,
  type: PropTypes.oneOf(['button', 'submit', 'reset']),
  ariaLabel: PropTypes.string,
  fullWidth: PropTypes.bool,
  className: PropTypes.string,
};
