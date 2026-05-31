import React from "react";
import { Eye, X } from "lucide-react";
import { API_BASE_URL, fetchJson } from "../../api.js";

function highlightEvidence(text, evidenceText) {
  if (!evidenceText) return text;

  const lowerText = text.toLowerCase();
  const lowerEvidence = evidenceText.toLowerCase();
  const index = lowerText.indexOf(lowerEvidence);

  if (index < 0) return text;

  return (
    <>
      {text.slice(0, index)}
      <mark>{text.slice(index, index + evidenceText.length)}</mark>
      {text.slice(index + evidenceText.length)}
    </>
  );
}

export default function ReviewContextModal({ evidence, fallbackChapter, onClose }) {
  const [radius, setRadius] = React.useState(1);
  const [contextData, setContextData] = React.useState(null);
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const chapterId = evidence?.chapter_id || fallbackChapter?.id;
  const evidenceText = evidence?.evidence_text || "";

  React.useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  React.useEffect(() => {
    let isCurrent = true;

    async function loadContext() {
      if (!chapterId) {
        setContextData(null);
        setError("No source chapter is attached to this evidence.");
        return;
      }

      setIsLoading(true);
      setError("");

      try {
        const params = new URLSearchParams({
          evidence: evidenceText,
          radius: String(radius),
        });
        const data = await fetchJson(`${API_BASE_URL}/admin/review/chapters/${chapterId}/context?${params.toString()}`);

        if (isCurrent) {
          setContextData(data);
        }
      } catch (err) {
        if (isCurrent) {
          setError(err.message || "Could not load source context.");
        }
      } finally {
        if (isCurrent) {
          setIsLoading(false);
        }
      }
    }

    loadContext();

    return () => {
      isCurrent = false;
    };
  }, [chapterId, evidenceText, radius]);

  const chapter = contextData?.chapter || fallbackChapter;

  return (
    <div className="review-context-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="review-context-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="review-context-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="review-context-header">
          <div>
            <span>Source Context</span>
            <h2 id="review-context-title">
              Chapter {chapter?.chapter_number || "-"}{chapter?.title ? ` - ${chapter.title}` : ""}
            </h2>
          </div>
          <button type="button" className="admin-icon-button" onClick={onClose} aria-label="Close context modal">
            <X size={17} />
          </button>
        </header>

        <div className="review-context-body">
          {isLoading ? (
            <p className="admin-muted">Loading context...</p>
          ) : error ? (
            <div className="review-context-miss">
              <strong>Could not load source context.</strong>
              <p>{error}</p>
            </div>
          ) : contextData?.exact_match ? (
            <div className="review-context-paragraphs">
              {contextData.paragraphs.map((paragraph) => (
                <p
                  key={paragraph.index}
                  className={paragraph.is_evidence ? "review-context-paragraph evidence" : "review-context-paragraph"}
                >
                  {paragraph.is_evidence
                    ? highlightEvidence(paragraph.text, contextData.evidence_text)
                    : paragraph.text}
                </p>
              ))}
            </div>
          ) : (
            <div className="review-context-miss">
              <strong>{contextData?.message || "Could not locate exact paragraph in chapter text."}</strong>
              <blockquote>{evidenceText || "No evidence snippet was attached."}</blockquote>
            </div>
          )}
        </div>

        <footer className="review-context-footer">
          <span>
            <Eye size={14} /> Showing {radius === 1 ? "nearby" : "expanded"} context only
          </span>
          {radius === 1 ? (
            <button type="button" className="admin-secondary-button" onClick={() => setRadius(2)}>
              Show More Context
            </button>
          ) : null}
        </footer>
      </section>
    </div>
  );
}
