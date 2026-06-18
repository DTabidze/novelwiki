import React from "react";
import { Building2, MapPin, Package, Route, Sparkles, Timeline, Users } from "lucide-react";
import WikiAvatar from "./WikiAvatar.jsx";
import { formatCultivationValue, formatNumber } from "../../utils/wikiFormat.js";

export default function WikiNovelOverview({
  characters,
  novel,
  onOpenCharacters,
  onOpenCultivation,
  onOpenItems,
  onOpenSkills,
  onSelectCharacter,
}) {
  const featuredCharacters = characters.slice(0, 4);
  const coveredChapters = novel.wiki_coverage_end_chapter || 0;
  const totalChapters = novel.chapter_count || 0;
  const browseCards = [
    { label: "Characters", count: novel.approved_character_count, subtitle: "View all characters", action: onOpenCharacters, Icon: Users, tone: "character" },
    { label: "Cultivation", count: novel.approved_progression_count, subtitle: "Explore progression", action: onOpenCultivation, Icon: Timeline, tone: "cultivation" },
    { label: "Skills", count: novel.approved_skill_count, subtitle: "View all skills", action: onOpenSkills, Icon: Sparkles, tone: "skill" },
    { label: "Items", count: novel.approved_item_count, subtitle: "View all items", action: onOpenItems, Icon: Package, tone: "item" },
    { label: "Organizations", count: 0, subtitle: "Coming later", action: null, Icon: Building2, tone: "organization" },
    { label: "Places", count: 0, subtitle: "Coming later", action: null, Icon: MapPin, tone: "place" },
    { label: "Timeline", count: 0, subtitle: "Major events later", action: null, Icon: Route, tone: "timeline" },
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
            <span className="author">Author: {novel.author || "Unknown"}</span>
            <span className="chapters" title={`The wiki currently covers data up to chapter ${formatNumber(coveredChapters)}.`}>
              Wiki Coverage: {formatNumber(coveredChapters)} / {formatNumber(totalChapters)} chapters
            </span>
          </div>
          <p>
            A structured public wiki built from reviewed extraction data. Browse approved
            characters, cultivation progression, skills, items, and future world entries.
          </p>
        </div>
      </section>

      <section className="wiki-card">
        <h2>Browse This Novel</h2>
        <div className="wiki-browse-grid">
          {browseCards.map(({ label, count, subtitle, action, Icon, tone }) => (
            <button
              className="wiki-browse-card"
              disabled={!action}
              key={label}
              type="button"
              onClick={action || undefined}
            >
              <span className={`wiki-browse-icon ${tone}`}>
                <Icon aria-hidden="true" size={20} strokeWidth={2.2} />
              </span>
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

      <section className="wiki-overview-grid single">
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
                <span>
                  {character.current_cultivation_level
                    ? formatCultivationValue(character.current_cultivation_level)
                    : character.current_position || "Character"}
                </span>
              </button>
            ))}
          </div>
        </div>
      </section>

    </article>
  );
}
