import PropTypes from 'prop-types';
import styles from './Textarea.module.css';

export default function Textarea({
  label = '',
  id,
  error = false,
  helperText = '',
  disabled = false,
  className = '',
  rows = 4,
  ...props
}) {
  const textareaClass = [styles.textarea, error ? styles.errorBorder : '', className]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={styles.wrapper}>
      {label && (
        <label htmlFor={id} className={styles.label}>
          {label}
        </label>
      )}
      <textarea
        id={id}
        rows={rows}
        disabled={disabled}
        className={textareaClass}
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

Textarea.propTypes = {
  label: PropTypes.string,
  id: PropTypes.string.isRequired,
  error: PropTypes.bool,
  helperText: PropTypes.string,
  disabled: PropTypes.bool,
  className: PropTypes.string,
  rows: PropTypes.number,
};
