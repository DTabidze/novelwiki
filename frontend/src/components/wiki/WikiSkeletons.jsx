import React from "react";

const SUMMARY_ROWS = Array.from({ length: 4 }, (_, index) => index);
const QUICK_FACT_ROWS = Array.from({ length: 9 }, (_, index) => index);
const TIMELINE_ROWS = Array.from({ length: 4 }, (_, index) => index);
const EVIDENCE_ROWS = Array.from({ length: 3 }, (_, index) => index);
const BROWSE_CARDS = Array.from({ length: 7 }, (_, index) => index);
const FEATURE_CARDS = Array.from({ length: 4 }, (_, index) => index);
const HERO_BADGES = Array.from({ length: 4 }, (_, index) => index);

export function SkeletonBlock({ className = "" }) {
  return <span aria-hidden="true" className={`wiki-skeleton ${className}`} />;
}

export function WikiNovelOverviewSkeleton() {
  return (
    <article className="wiki-novel-page" aria-busy="true">
      <section className="wiki-novel-hero">
        <div className="wiki-novel-cover">
          <SkeletonBlock className="wiki-detail-skeleton-cover-avatar" />
        </div>
        <div className="wiki-novel-info">
          <SkeletonBlock className="wiki-detail-skeleton-title" />
          <SkeletonBlock className="wiki-skeleton-badge" />
          <div className="wiki-novel-meta">
            <SkeletonBlock className="wiki-skeleton-meta-long" />
            <SkeletonBlock className="wiki-skeleton-meta-long" />
          </div>
          <SkeletonBlock className="wiki-skeleton-paragraph wide" />
          <SkeletonBlock className="wiki-skeleton-paragraph medium" />
        </div>
      </section>

      <section className="wiki-card">
        <h2>Browse This Novel</h2>
        <div className="wiki-browse-grid">
          {BROWSE_CARDS.map((row) => (
            <div className="wiki-browse-card wiki-skeleton-browse-card" key={row}>
              <SkeletonBlock className="wiki-index-skeleton-icon" />
              <div>
                <SkeletonBlock className="wiki-skeleton-title compact" />
                <SkeletonBlock className="wiki-skeleton-subtitle" />
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="wiki-overview-grid single">
        <div className="wiki-card">
          <div className="wiki-card-heading">
            <h2>Main Characters</h2>
          </div>
          <div className="wiki-character-card-grid">
            {FEATURE_CARDS.map((row) => (
              <div className="wiki-character-card wiki-skeleton-feature-card" key={row}>
                <SkeletonBlock className="wiki-index-skeleton-icon" />
                <SkeletonBlock className="wiki-skeleton-title compact" />
                <SkeletonBlock className="wiki-skeleton-subtitle" />
              </div>
            ))}
          </div>
        </div>
      </section>
    </article>
  );
}

export function WikiDetailSkeleton({ variant = "character" }) {
  if (variant === "character") {
    return <WikiCharacterDetailSkeleton />;
  }

  if (variant === "item") {
    return <WikiItemDetailSkeleton />;
  }

  return <WikiSkillDetailSkeleton />;
}

function WikiSkillDetailSkeleton() {
  return (
    <article className="wiki-skill-detail-page" aria-busy="true">
      <section className="wiki-character-hero-card wiki-entity-detail-hero-card skill">
        <div className="wiki-character-hero-avatar wiki-entity-detail-hero-avatar">
          <div className="wiki-skill-hero-avatar">
            <SkeletonBlock className="wiki-skill-hero-avatar-skeleton" />
          </div>
        </div>
        <div className="wiki-character-hero-main">
          <div className="wiki-title-row">
            <SkeletonBlock className="wiki-detail-skeleton-title" />
          </div>
          <div className="wiki-character-hero-badges">
            <SkeletonBlock className="wiki-skeleton-badge short" />
          </div>
          <SkeletonBlock className="wiki-skeleton-paragraph wide" />
          <SkeletonBlock className="wiki-character-hero-stats-skeleton-line" />
        </div>
      </section>

      <section>
        <WikiSkeletonCard title="Known Users" rows={3} />
      </section>

      <WikiSkeletonCard title="Aliases" rows={2} />
      <WikiTimelineSkeleton title="Usage Timeline" />
      <WikiEvidenceSkeleton />
    </article>
  );
}

function WikiItemDetailSkeleton() {
  return (
    <article className="wiki-skill-detail-page wiki-item-detail-page" aria-busy="true">
      <section className="wiki-character-hero-card wiki-entity-detail-hero-card item">
        <div className="wiki-character-hero-avatar wiki-entity-detail-hero-avatar">
          <div className="wiki-skill-hero-avatar">
            <SkeletonBlock className="wiki-skill-hero-avatar-skeleton" />
          </div>
        </div>
        <div className="wiki-character-hero-main">
          <div className="wiki-title-row">
            <SkeletonBlock className="wiki-detail-skeleton-title" />
          </div>
          <div className="wiki-character-hero-badges">
            <SkeletonBlock className="wiki-skeleton-badge short" />
          </div>
          <SkeletonBlock className="wiki-skeleton-paragraph wide" />
          <SkeletonBlock className="wiki-character-hero-stats-skeleton-line" />
        </div>
      </section>

      <WikiSkeletonCard title="Known Owners & Users" rows={3} />
      <WikiTimelineSkeleton title="Item Timeline" />
      <WikiEvidenceSkeleton />
    </article>
  );
}

function WikiCharacterDetailSkeleton() {
  return (
    <article className="wiki-character-page" aria-busy="true">
      <section className="wiki-character-hero-card">
        <div className="wiki-character-hero-avatar">
          <SkeletonBlock className="wiki-detail-skeleton-avatar" />
        </div>

        <div className="wiki-character-hero-main">
          <div className="wiki-title-row">
            <SkeletonBlock className="wiki-detail-skeleton-title" />
          </div>
          <div className="wiki-character-hero-badges wiki-character-hero-badges-skeleton">
            {HERO_BADGES.map((badge) => (
              <SkeletonBlock className={badge === 3 ? "wiki-skeleton-badge long" : "wiki-skeleton-badge"} key={badge} />
            ))}
          </div>
          <SkeletonBlock className="wiki-skeleton-paragraph wide" />
          <SkeletonBlock className="wiki-character-hero-stats-skeleton-line" />
        </div>
      </section>

      <section className="wiki-character-profile-grid">
        <div className="wiki-character-profile-main-column">
          <section className="wiki-card wiki-current-cultivation-card wiki-current-cultivation-skeleton-card">
            <SkeletonBlock className="wiki-current-cultivation-icon wiki-current-cultivation-icon-skeleton" />
            <div>
              <h2>Current Cultivation</h2>
              <SkeletonBlock className="wiki-skeleton-title compact" />
            </div>
          </section>

          <section className="wiki-card wiki-character-about-card wiki-character-about-skeleton-card">
            <h2>About</h2>
            <SkeletonBlock className="wiki-skeleton-paragraph wide" />
          </section>
        </div>

        <section className="wiki-card wiki-quick-facts-card wiki-quick-facts-skeleton-card">
          <h2>Quick Facts</h2>
          <div className="wiki-quick-facts-list">
            {QUICK_FACT_ROWS.map((row) => (
              <div className="wiki-quick-fact-row wiki-quick-fact-skeleton-row" key={row}>
                <div className="wiki-quick-fact-heading">
                  <SkeletonBlock className="wiki-fact-icon wiki-quick-fact-icon-skeleton" />
                  <SkeletonBlock className="wiki-skeleton-meta-short" />
                </div>
                <SkeletonBlock className="wiki-skeleton-meta-long" />
              </div>
            ))}
          </div>
        </section>
      </section>

      <section className="wiki-card wiki-relationships-card">
        <div className="wiki-card-heading">
          <h2>Relationships</h2>
        </div>
        <SkeletonBlock className="wiki-skeleton-paragraph medium" />
      </section>

      <section className="wiki-character-summary-grid">
        <WikiSkeletonCard title="Skills" />
        <WikiSkeletonCard title="Items" />
      </section>

      <WikiEvidenceSkeleton />
    </article>
  );
}

export function WikiSkeletonCard({ title, rows = 4 }) {
  return (
    <section className="wiki-card wiki-skeleton-section-card">
      <div className="wiki-card-heading">
        <h2>{title}</h2>
      </div>
      <div className="wiki-summary-list">
        {SUMMARY_ROWS.slice(0, rows).map((row) => (
          <div className="wiki-summary-row wiki-skeleton-summary-row" key={row}>
            <SkeletonBlock className="wiki-index-skeleton-icon" />
            <div>
              <SkeletonBlock className="wiki-skeleton-title compact" />
              <SkeletonBlock className="wiki-skeleton-subtitle" />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function WikiTimelineSkeleton({ title = "Timeline" }) {
  return (
    <section className="wiki-card wiki-skill-section-card">
      <div className="wiki-card-heading">
        <h2>{title}</h2>
      </div>
      <div className="wiki-skill-timeline">
        {TIMELINE_ROWS.map((row) => (
          <article className="wiki-skill-timeline-row wiki-skeleton-timeline-row" key={row}>
            <SkeletonBlock className="wiki-skill-timeline-dot" />
            <div>
              <SkeletonBlock className="wiki-skeleton-meta-short" />
              <SkeletonBlock className="wiki-skeleton-line" />
              <SkeletonBlock className="wiki-skeleton-paragraph wide" />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export function WikiEvidenceSkeleton() {
  return (
    <section className="wiki-card wiki-evidence-list-card">
      <div className="wiki-card-heading">
        <h2>Evidence Highlights</h2>
      </div>
      <div className="wiki-evidence-compact-list">
        {EVIDENCE_ROWS.map((row) => (
          <article className="wiki-evidence-compact-row wiki-skeleton-evidence-row" key={row}>
            <SkeletonBlock className="wiki-skeleton-badge short" />
            <SkeletonBlock className="wiki-skeleton-line" />
          </article>
        ))}
      </div>
    </section>
  );
}

export function WikiProgressionSkeleton() {
  return (
    <article className="wiki-cultivation-page" aria-busy="true">
      <section className="wiki-library-header compact">
        <SkeletonBlock className="wiki-skeleton-badge" />
        <SkeletonBlock className="wiki-detail-skeleton-title" />
        <SkeletonBlock className="wiki-skeleton-paragraph medium" />
      </section>
      <section className="wiki-card wiki-skill-section-card wiki-progression-skeleton-card">
        <div className="wiki-card-heading">
          <h2>Cultivation Timeline</h2>
        </div>
        <div className="wiki-skill-timeline">
          {TIMELINE_ROWS.map((row) => (
            <article className="wiki-skill-timeline-row wiki-skeleton-timeline-row" key={row}>
              <SkeletonBlock className="wiki-skill-timeline-dot" />
              <div>
                <SkeletonBlock className="wiki-skeleton-meta-short" />
                <SkeletonBlock className="wiki-skeleton-line" />
              </div>
            </article>
          ))}
        </div>
      </section>
    </article>
  );
}
