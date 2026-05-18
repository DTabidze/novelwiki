import React from "react";
import WikiAvatar from "./WikiAvatar.jsx";
import { formatDate, formatNumber } from "../../utils/wikiFormat.js";

export default function WikiNovelOverview({ characters, items, novel, onOpenCharacters, onSelectCharacter, skills }) {
  const featuredCharacters = characters.slice(0, 4);
  const featuredSkills = skills.slice(0, 2);
  const featuredItems = items.slice(0, 2);
  const browseCards = [
    ["Characters", novel.approved_character_count, "View all characters", onOpenCharacters],
    ["Cultivation", novel.approved_progression_count, "Explore progression", null],
    ["Skills", novel.approved_skill_count, "View all skills", null],
    ["Items", novel.approved_item_count, "View all items", null],
    ["Organizations", 0, "Coming later", null],
    ["Places", 0, "Coming later", null],
    ["Timeline", 0, "Major events later", null],
  ];

  return (
    <article className="wiki-novel-page">
      <section className="wiki-novel-hero">
        <div className="wiki-novel-cover">
          <WikiAvatar name={novel.title} />
        </div>
        <div className="wiki-novel-info">
          <h1>{novel.title}</h1>
          <span className="wiki-novel-tag">Cultivation Novel</span>
          <div className="wiki-novel-meta">
            <span>Author: Unknown</span>
            <span>Status: Tracking</span>
            <span>Chapters Tracked: {formatNumber(novel.chapter_count)}</span>
          </div>
          <p>
            A structured public wiki built from reviewed extraction data. Browse approved
            characters, cultivation progression, skills, items, and future world entries.
          </p>
        </div>
      </section>

      <section className="wiki-stats-bar">
        <div>
          <strong>{formatNumber(novel.chapter_count)}</strong>
          <span>Chapters</span>
        </div>
        <div>
          <strong>{formatNumber(novel.approved_character_count)}</strong>
          <span>Approved Characters</span>
        </div>
        <div>
          <strong>{formatNumber(novel.approved_progression_count)}</strong>
          <span>Progression Facts</span>
        </div>
        <div>
          <strong>{formatNumber(novel.approved_skill_count)}</strong>
          <span>Skills</span>
        </div>
        <div>
          <strong>{formatNumber(novel.approved_item_count)}</strong>
          <span>Items</span>
        </div>
      </section>

      <section className="wiki-overview-grid">
        <div className="wiki-card">
          <div className="wiki-card-heading">
            <h2>Main Characters</h2>
            <button className="wiki-text-link" type="button" onClick={onOpenCharacters}>
              View all characters
            </button>
          </div>
          <div className="wiki-character-card-grid">
            {featuredCharacters.map((character) => (
              <button
                className="wiki-character-card"
                key={character.id}
                type="button"
                onClick={() => onSelectCharacter(character)}
              >
                <WikiAvatar name={character.name} size="small" />
                <strong>{character.name}</strong>
                <span>{character.current_cultivation_level || character.current_position || "Character"}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="wiki-card">
          <h2>Data & Tracking Status</h2>
          <div className="wiki-status-list">
            <div>
              <span>Last updated</span>
              <strong>{formatDate(novel.updated_at)}</strong>
            </div>
            <div>
              <span>Approved entries</span>
              <strong>{formatNumber(novel.approved_entry_count)}</strong>
            </div>
            <div>
              <span>Pending review</span>
              <strong>{formatNumber(novel.pending_review_count)}</strong>
            </div>
            <div>
              <span>Coverage</span>
              <strong>Up to {formatNumber(novel.chapter_count)} chapters</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="wiki-card">
        <h2>Browse This Novel</h2>
        <div className="wiki-browse-grid">
          {browseCards.map(([label, count, subtitle, action]) => (
            <button
              className="wiki-browse-card"
              disabled={!action}
              key={label}
              type="button"
              onClick={action || undefined}
            >
              <span>{label.slice(0, 1)}</span>
              <div>
                <strong>{label}</strong>
                <small>
                  {formatNumber(count)} {subtitle}
                </small>
              </div>
            </button>
          ))}
        </div>
      </section>

      {(featuredSkills.length > 0 || featuredItems.length > 0) && (
        <section className="wiki-overview-grid compact">
          <div className="wiki-card">
            <h2>Featured Skills</h2>
            {featuredSkills.map((skill) => (
              <div className="wiki-mini-link" key={skill.id}>
                <strong>{skill.name}</strong>
                <span>{skill.category || "Skill"}</span>
              </div>
            ))}
          </div>
          <div className="wiki-card">
            <h2>Featured Items</h2>
            {featuredItems.map((item) => (
              <div className="wiki-mini-link" key={item.id}>
                <strong>{item.name}</strong>
                <span>{item.category || "Item"}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </article>
  );
}
