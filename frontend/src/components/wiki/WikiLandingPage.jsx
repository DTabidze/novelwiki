import React from "react";
import WikiAvatar from "./WikiAvatar.jsx";
import { formatDate, formatNumber } from "../../utils/wikiFormat.js";

export default function WikiLandingPage({ novels, onLoadNovel }) {
  return (
    <article className="wiki-landing-page wiki-novel-library">
      <section className="wiki-library-header">
        <h1>Novels</h1>
        <p>Browse and explore cultivation novels with automatically extracted wiki data.</p>
      </section>

      <section className="wiki-library-toolbar">
        <input type="search" placeholder="Search novels..." />
        <select defaultValue="all">
          <option value="all">Status: All</option>
          <option value="tracking">Tracking</option>
          <option value="complete">Complete</option>
        </select>
        <select defaultValue="all">
          <option value="all">Chapters: All</option>
          <option value="short">Under 250</option>
          <option value="long">250+</option>
        </select>
        <select defaultValue="recent">
          <option value="recent">Recently Updated</option>
          <option value="title">Title</option>
        </select>
        <span>{formatNumber(novels.length)} novels</span>
      </section>

      <section className="wiki-card wiki-novel-table-card">
        {novels.length === 0 ? <p>No novels available yet.</p> : null}
        <div className="wiki-novel-table">
          <div className="wiki-novel-table-head">
            <span>Novel</span>
            <span>Author</span>
            <span>Status</span>
            <span>Chapters</span>
            <span>Last Updated</span>
            <span>Actions</span>
          </div>
          {novels.map((wikiNovel) => (
            <button
              className="wiki-novel-row"
              key={wikiNovel.id}
              type="button"
              onClick={() => onLoadNovel(wikiNovel.id)}
            >
              <div className="wiki-novel-row-title">
                <WikiAvatar name={wikiNovel.title} size="tiny" />
                <div>
                  <strong>{wikiNovel.title}</strong>
                  <small>Cultivation Novel</small>
                </div>
              </div>
              <span>{wikiNovel.author || "Unknown"}</span>
              <span className="wiki-status-tag">Completed</span>
              <strong>{formatNumber(wikiNovel.chapter_count)}</strong>
              <span>{formatDate(wikiNovel.updated_at)}</span>
              <span className="wiki-row-action">›</span>
            </button>
          ))}
        </div>
      </section>
    </article>
  );
}
