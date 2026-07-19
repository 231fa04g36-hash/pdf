import PropTypes from 'prop-types';
import { BookOpen } from 'lucide-react';
import { useConversationStore } from '../../../stores/conversationStore';
import styles from './SourceCitation.module.css';

export default function SourceCitation({ citations }) {
  const { setActiveCitation } = useConversationStore();

  if (!citations || citations.length === 0) return null;

  return (
    <div className={styles.container}>
      <div className={styles.title}>Sources Cited:</div>
      <div className={styles.list}>
        {citations.map((cit, idx) => (
          <button
            key={idx}
            type="button"
            className={styles.pill}
            onClick={() => setActiveCitation(cit)}
            title={cit.snippet}
          >
            <BookOpen size={10} />
            <span>Page {cit.page}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

SourceCitation.propTypes = {
  citations: PropTypes.arrayOf(
    PropTypes.shape({
      page: PropTypes.number.isRequired,
      snippet: PropTypes.string.isRequired,
    })
  ).isRequired,
};
