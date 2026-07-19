import PropTypes from 'prop-types';
import styles from './Input.module.css';

export default function Input({
  label = '',
  id,
  error = false,
  helperText = '',
  disabled = false,
  className = '',
  type = 'text',
  ...props
}) {
  const inputClass = [styles.input, error ? styles.errorBorder : '', className]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={styles.wrapper}>
      {label && (
        <label htmlFor={id} className={styles.label}>
          {label}
        </label>
      )}
      <input
        id={id}
        type={type}
        disabled={disabled}
        className={inputClass}
        aria-invalid={error ? 'true' : 'false'}
        aria-describedby={helperText ? `${id}-helper` : undefined}
        {...props}
      />
      {helperText && (
        <span
          id={`${id}-helper`}
          className={`${styles.helperText} ${error ? styles.errorText : ''}`}
        >
          {helperText}
        </span>
      )}
    </div>
  );
}

Input.propTypes = {
  label: PropTypes.string,
  id: PropTypes.string.isRequired,
  error: PropTypes.bool,
  helperText: PropTypes.string,
  disabled: PropTypes.bool,
  className: PropTypes.string,
  type: PropTypes.string,
};
