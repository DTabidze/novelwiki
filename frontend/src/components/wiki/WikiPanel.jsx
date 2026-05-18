import React from "react";
import { Link, useNavigate } from "react-router-dom";
import WikiAvatar from "./WikiAvatar.jsx";
import WikiCharacterBrowser from "./WikiCharacterBrowser.jsx";
import WikiCharacterDetail from "./WikiCharacterDetail.jsx";
import WikiLandingPage from "./WikiLandingPage.jsx";
import WikiNovelOverview from "./WikiNovelOverview.jsx";

export default function WikiPanel({
  characters,
  items,
  page,
  loading,
  novel,
  novels,
  onLoadNovel,
  onOpenAdmin,
  onSelectCharacter,
  selectedCharacter,
  selectedNovelId,
  skills,
}) {
  const navigate = useNavigate();
  const trackedNovel = novel;
  const activeSection = !trackedNovel ? "Novels" : page === "Character" ? "Characters" : page;
  const globalNav = ["Novels", "Recent Updates", "Bookmarks", "About"];
  const novelNav = ["Novels", "Overview", "Characters", "Cultivation", "Skills", "Items", "Organizations", "Places", "Timeline"];

  function openNovel(novelId) {
    navigate(`/wiki/novels/${novelId}`);
  }

  function openCharacters() {
    if (trackedNovel) {
      navigate(`/wiki/novels/${trackedNovel.id}/characters`);
    }
  }

  function openCharacter(character) {
    if (trackedNovel) {
      navigate(`/wiki/novels/${trackedNovel.id}/characters/${character.id}`);
    }
  }

  function handleNav(label) {
    if (label === "Novels") {
      navigate("/wiki/novels");
      return;
    }

    if (!trackedNovel) {
      return;
    }

    if (label === "Overview") {
      navigate(`/wiki/novels/${trackedNovel.id}`);
      return;
    }

    if (label === "Characters") {
      openCharacters();
    }
  }

  return (
    <section className="wiki-app">
      <aside className="wiki-sidebar">
        <div className="wiki-brand">
          <div className="wiki-logo">NW</div>
          <strong>Cultivation Wiki</strong>
          <span>Explore the Dao</span>
        </div>

        <input className="wiki-sidebar-search" type="search" placeholder="Search wiki..." />

        <nav className="wiki-nav">
          {(trackedNovel ? novelNav : globalNav).map((label) => (
            <button
              className={label === activeSection ? "active" : ""}
              disabled={
                Boolean(trackedNovel) &&
                !["Novels", "Overview", "Characters"].includes(label)
              }
              key={label}
              type="button"
              onClick={() => handleNav(label)}
            >
              <span>{label.slice(0, 1)}</span>
              {label}
            </button>
          ))}
        </nav>

        <div className="wiki-sidebar-section">
          <div className="wiki-sidebar-title">
            <span>{trackedNovel ? "Selected Novel" : "Novel Context"}</span>
            <button type="button" onClick={onOpenAdmin}>
              Admin
            </button>
          </div>
          {trackedNovel ? (
            <button
              className="wiki-tracked-novel active"
              type="button"
              onClick={() => openNovel(trackedNovel.id)}
            >
              <WikiAvatar name={trackedNovel.title} size="tiny" />
              <span>{trackedNovel.title}</span>
              <small>{trackedNovel.approved_character_count} characters</small>
            </button>
          ) : (
            <p className="wiki-sidebar-context-empty">
              Select a novel from the main list to browse its characters, skills, and progression.
            </p>
          )}
        </div>
      </aside>

      <div className="wiki-main">
        <header className="wiki-topbar">
          <div className="wiki-breadcrumb">
            <Link to="/wiki/novels">Home</Link>
            <span>/</span>
            <Link to="/wiki/novels">Novels</Link>
            {trackedNovel ? (
              <>
                <span>/</span>
                <Link to={`/wiki/novels/${trackedNovel.id}`}>{trackedNovel.title}</Link>
              </>
            ) : null}
            {page === "Characters" ? (
              <>
                <span>/</span>
                <strong>Characters</strong>
              </>
            ) : null}
            {page === "Character" && selectedCharacter ? (
              <>
                <span>/</span>
                <Link to={`/wiki/novels/${trackedNovel.id}/characters`}>Characters</Link>
                <span>/</span>
                <strong>{selectedCharacter.name}</strong>
              </>
            ) : null}
          </div>
          <input className="wiki-search" type="search" placeholder="Search characters, novels, skills..." />
        </header>

        <div className="wiki-content">
          {!trackedNovel ? (
            <WikiLandingPage novels={novels} onLoadNovel={openNovel} />
          ) : null}

          {loading ? <p className="wiki-loading">Loading wiki data...</p> : null}

          {trackedNovel ? (
            <>
              <section className="wiki-browser-strip">
                <div>
                  <strong>{trackedNovel.title}</strong>
                  <span>
                    {trackedNovel.approved_character_count} characters / {trackedNovel.approved_skill_count} skills /{" "}
                    {trackedNovel.approved_item_count} items
                  </span>
                </div>
                <div className="wiki-entity-tabs">
                  <select
                    value={selectedCharacter ? selectedCharacter.id : ""}
                    onChange={(event) => {
                      if (!event.target.value) {
                        navigate(`/wiki/novels/${trackedNovel.id}`);
                        return;
                      }

                      const character = characters.find((item) => item.id === Number(event.target.value));
                      if (character) {
                        openCharacter(character);
                      }
                    }}
                  >
                    <option value="">Select character...</option>
                    {characters.map((character) => (
                      <option key={character.id} value={character.id}>
                        {character.name}
                      </option>
                    ))}
                  </select>
                </div>
              </section>

              {page === "Character" && selectedCharacter ? (
                <WikiCharacterDetail
                  character={selectedCharacter}
                  relatedCharacters={characters}
                  onSelectRelated={openCharacter}
                />
              ) : null}

              {page === "Characters" ? (
                <WikiCharacterBrowser
                  characters={characters}
                  novel={trackedNovel}
                  onSelectCharacter={openCharacter}
                />
              ) : null}

              {page === "Overview" ? (
                <WikiNovelOverview
                  characters={characters}
                  items={items}
                  novel={trackedNovel}
                  onOpenCharacters={openCharacters}
                  onSelectCharacter={openCharacter}
                  skills={skills}
                />
              ) : null}
            </>
          ) : null}
        </div>
      </div>
    </section>
  );
}
