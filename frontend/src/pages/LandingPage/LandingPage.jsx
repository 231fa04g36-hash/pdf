import { useNavigate } from 'react-router-dom';
import { useEffect } from 'react';
import { UploadCloud, MessageSquare, CheckSquare, FileText, PlayCircle, Search, Sun, Moon } from 'lucide-react';
import PropTypes from 'prop-types';
import Button from '../../components/shared/Button/Button';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import styles from './LandingPage.module.css';

function GithubIcon({ size = 20, ...props }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      stroke="currentColor"
      strokeWidth="2"
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
    </svg>
  );
}

GithubIcon.propTypes = {
  size: PropTypes.number,
};

function LinkedinIcon({ size = 20, ...props }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      stroke="currentColor"
      strokeWidth="2"
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />
      <rect x="2" y="9" width="4" height="12" />
      <circle cx="4" cy="4" r="2" />
    </svg>
  );
}

LinkedinIcon.propTypes = {
  size: PropTypes.number,
};

export default function LandingPage() {
  const navigate = useNavigate();
  const { signInWithGoogle, user } = useAuth();
  const { theme, toggleTheme } = useTheme();

  useEffect(() => {
    if (user) {
      navigate('/app', { replace: true });
    }
  }, [user, navigate]);

  const handleTryDemo = () => {
    navigate('/app');
  };

  const handleSignIn = async () => {
    try {
      await signInWithGoogle();
    } catch (err) {
      // Handled and toasted by AuthContext
    }
  };

  return (
    <div className={styles.page}>
      {/* Sticky Header */}
      <header className={styles.header}>
        <div className={`${styles.container} ${styles.nav}`}>
          <a href="/" className={styles.logo}>
            <FileText className={styles.logoIcon} size={28} />
            <span>PDF Chatbot</span>
          </a>
          <nav className={styles.navLinks}>
            <a href="#features" className={styles.navLink}>Features</a>
            <a href="#architecture" className={styles.navLink}>Architecture</a>
            <a href="https://github.com" target="_blank" rel="noopener noreferrer" className={styles.navLink}>GitHub</a>
          </nav>
          <div className={styles.navButtons}>
            <button
              type="button"
              className={styles.themeToggle}
              onClick={toggleTheme}
              title={theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
              aria-label="Toggle theme mode"
            >
              {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
            </button>
            <Button variant="secondary" size="sm" onClick={handleTryDemo}>
              Try the Demo
            </Button>
            <Button variant="primary" size="sm" onClick={handleSignIn}>
              Sign In
            </Button>
          </div>
        </div>
      </header>

      <main className={styles.main}>
        {/* Hero Section */}
        <section className={`${styles.container} ${styles.hero}`}>
          <h1 className={styles.headline}>
            Chat with any PDF — get grounded, cited answers instantly
          </h1>
          <p className={styles.subheadline}>
            Upload any PDF and ask questions in natural language. Get accurate, context-aware answers powered by RAG.
          </p>
          <div className={styles.ctaGroup}>
            <Button variant="primary" size="lg" onClick={handleTryDemo}>
              Try the Demo
            </Button>
            <Button variant="secondary" size="lg" onClick={handleSignIn}>
              Sign In
            </Button>
          </div>
          {/* Product Preview Screenshot Mockup */}
          <div className={styles.previewContainer}>
            <img 
              src="/product_preview.png" 
              alt="PDF Chatbot Interface Preview" 
              className={styles.previewImage} 
            />
          </div>
        </section>

        {/* Features Section */}
        <section id="features" className={styles.featuresSection}>
          <div className={styles.container}>
            <div className={styles.featuresGrid}>
              <div className={styles.featureCard}>
                <div className={styles.featureIcon}>
                  <Search size={24} />
                </div>
                <h3 className={styles.featureTitle}>Semantic Search</h3>
                <p className={styles.featureDesc}>
                  Find answers based on semantic meaning and context, not just simple keyword matching.
                </p>
              </div>

              <div className={styles.featureCard}>
                <div className={styles.featureIcon}>
                  <CheckSquare size={24} />
                </div>
                <h3 className={styles.featureTitle}>Source Citations</h3>
                <p className={styles.featureDesc}>
                  Every response is grounded in facts and links back to the exact page of your PDF document.
                </p>
              </div>

              <div className={styles.featureCard}>
                <div className={styles.featureIcon}>
                  <MessageSquare size={24} />
                </div>
                <h3 className={styles.featureTitle}>Context-Aware Chat</h3>
                <p className={styles.featureDesc}>
                  Ask follow-up questions in a continuous conversation, preserving the document context.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Tech Stack Badges Row */}
        <section className={styles.badgesSection}>
          <div className={styles.container}>
            <h4 className={styles.badgesTitle}>Powered by Open Source AI</h4>
            <div className={styles.badgesGrid}>
              <div className={styles.badge}>React 18</div>
              <div className={styles.badge}>FastAPI</div>
              <div className={styles.badge}>ChromaDB</div>
              <div className={styles.badge}>Sentence Transformers</div>
              <div className={styles.badge}>Ollama / OpenAI</div>
            </div>
          </div>
        </section>

        {/* Explainer (How it Works) */}
        <section id="architecture" className={styles.explainerSection}>
          <div className={styles.container}>
            <h2 className={styles.explainerTitle}>How it works under the hood</h2>
            <div className={styles.explainerGrid}>
              <div className={styles.explainerText}>
                <p className={styles.explainerParagraph}>
                  Traditional LLMs often struggle with document-specific queries. Our PDF Chatbot uses Retrieval-Augmented Generation (RAG) to retrieve relevant context from your uploaded PDFs before generating every response.
                </p>
                <div className={styles.emojiFlowContainer}>
                  <div className={styles.emojiStep}>
                    <span className={styles.emojiIcon}>📄</span>
                    <span className={styles.emojiLabel}>PDF</span>
                  </div>
                  <div className={styles.emojiArrow}>&rarr;</div>
                  <div className={styles.emojiStep}>
                    <span className={styles.emojiIcon}>✂️</span>
                    <span className={styles.emojiLabel}>Chunks</span>
                  </div>
                  <div className={styles.emojiArrow}>&rarr;</div>
                  <div className={styles.emojiStep}>
                    <span className={styles.emojiIcon}>🔢</span>
                    <span className={styles.emojiLabel}>Embeddings</span>
                  </div>
                  <div className={styles.emojiArrow}>&rarr;</div>
                  <div className={styles.emojiStep}>
                    <span className={styles.emojiIcon}>🗄️</span>
                    <span className={styles.emojiLabel}>ChromaDB</span>
                  </div>
                  <div className={styles.emojiArrow}>&rarr;</div>
                  <div className={styles.emojiStep}>
                    <span className={styles.emojiIcon}>🔍</span>
                    <span className={styles.emojiLabel}>Retrieval</span>
                  </div>
                  <div className={styles.emojiArrow}>&rarr;</div>
                  <div className={styles.emojiStep}>
                    <span className={styles.emojiIcon}>🤖</span>
                    <span className={styles.emojiLabel}>LLM</span>
                  </div>
                  <div className={styles.emojiArrow}>&rarr;</div>
                  <div className={styles.emojiStep}>
                    <span className={styles.emojiIcon}>✅</span>
                    <span className={styles.emojiLabel}>Answer</span>
                  </div>
                </div>
              </div>
              <div className={styles.diagramContainer}>
                {/* Phase 1: Ingestion */}
                <div className={styles.diagramPhase}>
                  <h4 className={styles.phaseTitle}>1. Document Ingestion Flow (One-time)</h4>
                  <div className={styles.flowRow}>
                    <div className={styles.diagramBlock} title="User uploads a PDF file through the chatbot interface">
                      <span className={styles.stepNum}>Step 1</span>
                      <strong>PDF Upload</strong>
                      <span className={styles.stepDesc}>Extract raw text & pages</span>
                    </div>
                    <div className={styles.diagramArrow}>&rarr;</div>
                    <div className={styles.diagramBlock} title="Divide raw document text into smaller overlapping chunks to maintain local context">
                      <span className={styles.stepNum}>Step 2</span>
                      <strong>Text Chunking</strong>
                      <span className={styles.stepDesc}>Split into small passages</span>
                    </div>
                    <div className={styles.diagramArrow}>&rarr;</div>
                    <div className={styles.diagramBlock} title="Transform text chunks into dense vectors representing mathematical semantics">
                      <span className={styles.stepNum}>Step 3</span>
                      <strong>Vector Embeddings</strong>
                      <span className={styles.stepDesc}>Generate semantic vector</span>
                    </div>
                    <div className={styles.diagramArrow}>&rarr;</div>
                    <div className={styles.diagramBlock} title="Store vectors and original chunks inside ChromaDB database for rapid queries">
                      <span className={styles.stepNum}>Step 4</span>
                      <strong>ChromaDB Store</strong>
                      <span className={styles.stepDesc}>Index chunks & vectors</span>
                    </div>
                  </div>
                </div>

                {/* Phase 2: Chat / RAG */}
                <div className={styles.diagramPhase}>
                  <h4 className={styles.phaseTitle}>2. Retrieval-Augmented Generation (On every query)</h4>
                  <div className={styles.flowRow}>
                    <div className={styles.diagramBlock} title="User types a message or query in the chat input">
                      <span className={styles.stepNum}>Step A</span>
                      <strong>User Question</strong>
                      <span className={styles.stepDesc}>Input query in chat</span>
                    </div>
                    <div className={styles.diagramArrow}>&rarr;</div>
                    <div className={styles.diagramBlock} title="Convert question to vector and search ChromaDB using similarity search">
                      <span className={styles.stepNum}>Step B</span>
                      <strong>Semantic Retrieval</strong>
                      <span className={styles.stepDesc}>Retrieve top-k similar chunks from ChromaDB</span>
                    </div>
                    <div className={styles.diagramArrow}>&rarr;</div>
                    <div className={styles.diagramBlock} title="Combine the retrieved text passages with the user's original query into a final prompt template">
                      <span className={styles.stepNum}>Step C</span>
                      <strong>Prompt Augmentation</strong>
                      <span className={styles.stepDesc}>Combine retrieved context + user query</span>
                    </div>
                    <div className={styles.diagramArrow}>&rarr;</div>
                    <div className={styles.diagramBlock} title="LLM parses the augmented prompt to generate a cited response directly grounded in the PDF facts">
                      <span className={styles.stepNum}>Step D</span>
                      <strong>Grounded Answer</strong>
                      <span className={styles.stepDesc}>LLM generates cited answer using retrieved context</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

      </main>

    </div>
  );
}
