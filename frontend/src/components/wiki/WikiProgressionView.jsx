import React from "react";
import { chapterLabel, formatCultivationValue, splitCultivationValue } from "../../utils/wikiFormat.js";

function chapterNumber(event) {
  return event.chapter ? event.chapter.chapter_number : 0;
}

function eventRank(event) {
  if (event.progression_type === "cultivation_level") {
    return 0;
  }

  return 1;
}

function conciseDescription(event) {
  const description = (event.description || "").trim();

  if (!description) {
    return "";
  }

  const value =
    event.progression_type === "cultivation_level"
      ? formatCultivationValue(event.new_value).toLowerCase()
      : (event.new_value || "").toLowerCase();
  const lowerDescription = description.toLowerCase();
  const repetitiveStarts = [
    "reached ",
    "advanced to ",
    "achieved ",
    "has reached ",
    "successfully reached ",
  ];

  if (
    value &&
    lowerDescription.includes(value) &&
    repetitiveStarts.some((prefix) => lowerDescription.startsWith(prefix))
  ) {
    return "";
  }

  return description;
}

function groupChronologically(events) {
  const timelineEvents = events
    .filter((event) => ["cultivation_level", "position"].includes(event.progression_type))
    .sort((first, second) => {
      const chapterDifference = chapterNumber(first) - chapterNumber(second);

      if (chapterDifference !== 0) {
        return chapterDifference;
      }

      return eventRank(first) - eventRank(second);
    });

  const groups = [];
  let currentRealm = "Advancements Before Confirmed Realm";

  timelineEvents.forEach((event) => {
    if (event.progression_type === "cultivation_level") {
      currentRealm = splitCultivationValue(event.new_value).realm;
    }

    let group = groups.find((candidate) => candidate.realm === currentRealm);

    if (!group) {
      group = { realm: currentRealm, events: [] };
      groups.push(group);
    }

    group.events.push(event);
  });

  return groups;
}

export default function WikiProgressionView({ events }) {
  const timelineEvents = events.filter((event) =>
    ["cultivation_level", "position"].includes(event.progression_type)
  );
  const groups = groupChronologically(events);

  return (
    <section className="wiki-progression-timeline-card">
      {timelineEvents.length === 0 ? <p>No approved cultivation or position progression yet.</p> : null}
      {groups.map((group) => (
        <section className="wiki-timeline-realm" key={group.realm}>
          <h2>{group.realm}</h2>
          <div className="wiki-journey-timeline">
            {group.events.map((event) => {
              const isCultivation = event.progression_type === "cultivation_level";
              const description = conciseDescription(event);
              const eventValue = isCultivation ? formatCultivationValue(event.new_value) : event.new_value;
              const oldValue = isCultivation ? formatCultivationValue(event.old_value) : event.old_value;

              return (
                <article
                  className={isCultivation ? "wiki-journey-event cultivation" : "wiki-journey-event position"}
                  key={event.id}
                >
                  <small>{chapterLabel(event.chapter)}</small>
                  <span className="wiki-journey-node" />
                  <div className="wiki-journey-card">
                    <div>
                      <strong>{eventValue}</strong>
                      <span>{isCultivation ? "Cultivation Breakthrough" : "Position Advancement"}</span>
                    </div>
                    {oldValue ? <p>From {oldValue}</p> : null}
                    {description ? <p>{description}</p> : null}
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      ))}
    </section>
  );
}
