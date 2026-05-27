import React from "react";
import ExtractionRunCard from "./ExtractionRunCard.jsx";

export default function ExtractionRunsPanel({ extractionRuns, onNewExtraction }) {
  return (
    <section className="admin-panel extraction-runs-panel">
      <div className="admin-section-header">
        <div>
          <h2>All Extraction Runs</h2>
          <p>Recent processing jobs and outcomes.</p>
        </div>
        <button type="button" onClick={onNewExtraction}>New Extraction</button>
      </div>
      <div className="extraction-run-list">
        {extractionRuns.length ? (
          extractionRuns.slice(0, 8).map((run) => <ExtractionRunCard key={run.id} run={run} />)
        ) : (
          <p className="admin-muted">No extraction runs yet.</p>
        )}
      </div>
    </section>
  );
}
