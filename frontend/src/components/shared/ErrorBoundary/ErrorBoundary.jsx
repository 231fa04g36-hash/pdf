import { Component } from 'react';
import PropTypes from 'prop-types';
import { AlertOctagon } from 'lucide-react';
import Button from '../Button/Button';
import styles from './ErrorBoundary.module.css';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an unhandled render error:', error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className={styles.overlay}>
          <div className={styles.card}>
            <div className={styles.icon}>
              <AlertOctagon size={32} />
            </div>
            <h1 className={styles.title}>Something went wrong</h1>
            <p className={styles.desc}>An unexpected error occurred while rendering this page.</p>
            {this.state.error && (
              <pre className={styles.details}>{this.state.error.toString()}</pre>
            )}
            <Button variant="primary" onClick={this.handleReload}>
              Reload Page
            </Button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

ErrorBoundary.propTypes = {
  children: PropTypes.node.isRequired,
};
