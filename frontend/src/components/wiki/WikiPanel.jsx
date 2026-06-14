import React from "react";
import {
  Bookmark,
  Building2,
  CircleHelp,
  Compass,
  Home,
  Library,
  MapPin,
  Package,
  ScrollText,
  Sparkles,
  Timeline,
  Users,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import WikiAccountControls from "./WikiAccountControls.jsx";
import WikiAvatar from "./WikiAvatar.jsx";
import WikiCharacterBrowser from "./WikiCharacterBrowser.jsx";
import WikiCharacterDetail from "./WikiCharacterDetail.jsx";
import WikiCharacterProgressionPage from "./WikiCharacterProgressionPage.jsx";
import WikiCultivationPage from "./WikiCultivationPage.jsx";
import WikiGlobalSearch from "./WikiGlobalSearch.jsx";
import WikiItemsIndex from "./WikiItemsIndex.jsx";
import WikiItemPage from "./WikiItemPage.jsx";
import WikiLandingPage from "./WikiLandingPage.jsx";
import WikiNovelOverview from "./WikiNovelOverview.jsx";
import WikiSearchResultsPage from "./WikiSearchResultsPage.jsx";
import WikiSkillPage from "./WikiSkillPage.jsx";
import WikiSkillsIndex from "./WikiSkillsIndex.jsx";

const WIKI_NAV_ICONS = {
  About: CircleHelp,
  Bookmarks: Bookmark,
  Characters: Users,
  Cultivation: Timeline,
  Items: Package,
  Novels: Library,
  Organizations: Building2,
  Overview: Home,
  Places: MapPin,
  "Recent Updates": ScrollText,
  Skills: Sparkles,
  Timeline,
};

export default function WikiPanel({
  characters,
  items,
  page,
  progressionEvents = [],
  loading,
  novel,
  novels,
  onLoadNovel,
  onSelectCharacter,
  selectedCharacter,
  selectedItem,
  selectedNovelId,
  selectedSkill,
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

  function openCultivation() {
    if (trackedNovel) {
      navigate(`/wiki/novels/${trackedNovel.id}/cultivation`);
    }
  }

  function openCharacter(character) {
    if (trackedNovel) {
      navigate(`/wiki/novels/${trackedNovel.id}/characters/${character.id}`);
    }
  }

  function openCharacterProgression(character) {
    if (trackedNovel && character) {
      navigate(`/wiki/novels/${trackedNovel.id}/characters/${character.id}/progression`);
    }
  }

  function openSkills() {
    if (trackedNovel) {
      navigate(`/wiki/novels/${trackedNovel.id}/skills`);
    }
  }

  function openCharacterSkills(character) {
    if (trackedNovel && character) {
      navigate(`/wiki/novels/${trackedNovel.id}/skills?character_id=${character.id}`);
    }
  }

  function openSkill(skill) {
    if (trackedNovel) {
      navigate(`/wiki/novels/${trackedNovel.id}/skills/${skill.id}`);
    }
  }

  function openItems() {
    if (trackedNovel) {
      navigate(`/wiki/novels/${trackedNovel.id}/items`);
    }
  }

  function openCharacterItems(character) {
    if (trackedNovel && character) {
      navigate(`/wiki/novels/${trackedNovel.id}/items?character_id=${character.id}`);
    }
  }

  function openItem(item) {
    if (trackedNovel) {
      navigate(`/wiki/novels/${trackedNovel.id}/items/${item.id}`);
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
      return;
    }

    if (label === "Cultivation") {
      openCultivation();
      return;
    }

    if (label === "Skills") {
      openSkills();
      return;
    }

    if (label === "Items") {
      openItems();
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

        <nav className="wiki-nav">
          {(trackedNovel ? novelNav : globalNav).map((label) => {
            const Icon = WIKI_NAV_ICONS[label] || Compass;

            return (
              <button
                className={label === activeSection ? "active" : ""}
                disabled={
                  Boolean(trackedNovel) &&
                  !["Novels", "Overview", "Characters", "Cultivation", "Skills", "Items"].includes(label)
                }
                key={label}
                type="button"
                onClick={() => handleNav(label)}
              >
                <span className="wiki-nav-icon">
                  <Icon aria-hidden="true" size={14} strokeWidth={2} />
                </span>
                {label}
              </button>
            );
          })}
        </nav>

        <div className="wiki-sidebar-section">
          <div className="wiki-sidebar-title">
            <span>{trackedNovel ? "Selected Novel" : "Novel Context"}</span>
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
            {page === "Skills" ? (
              <>
                <span>/</span>
                <strong>Skills</strong>
              </>
            ) : null}
            {page === "Cultivation" ? (
              <>
                <span>/</span>
                <strong>Cultivation</strong>
              </>
            ) : null}
            {page === "Search" ? (
              <>
                <span>/</span>
                <strong>Search</strong>
              </>
            ) : null}
            {page === "Skill" && selectedSkill ? (
              <>
                <span>/</span>
                <Link to={`/wiki/novels/${trackedNovel.id}/skills`}>Skills</Link>
                <span>/</span>
                <strong>{selectedSkill.name}</strong>
              </>
            ) : null}
            {page === "Items" ? (
              <>
                <span>/</span>
                <strong>Items</strong>
              </>
            ) : null}
            {page === "Item" && selectedItem ? (
              <>
                <span>/</span>
                <Link to={`/wiki/novels/${trackedNovel.id}/items`}>Items</Link>
                <span>/</span>
                <strong>{selectedItem.name}</strong>
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
            {page === "CharacterProgression" && selectedCharacter ? (
              <>
                <span>/</span>
                <Link to={`/wiki/novels/${trackedNovel.id}/characters`}>Characters</Link>
                <span>/</span>
                <Link to={`/wiki/novels/${trackedNovel.id}/characters/${selectedCharacter.id}`}>
                  {selectedCharacter.name}
                </Link>
                <span>/</span>
                <strong>Progression</strong>
              </>
            ) : null}
          </div>
          <div className="wiki-topbar-actions">
            <WikiGlobalSearch
              characters={characters}
              items={items}
              novel={trackedNovel}
              skills={skills}
              onSelectCharacter={openCharacter}
              onSelectItem={openItem}
              onSelectSkill={openSkill}
            />
            <WikiAccountControls />
          </div>
        </header>

        <div className="wiki-content">
          {!trackedNovel ? (
            <WikiLandingPage novels={novels} onLoadNovel={openNovel} />
          ) : null}

          {loading ? <p className="wiki-loading">Loading wiki data...</p> : null}

          {trackedNovel ? (
            <>
              {page === "Character" && selectedCharacter ? (
                <WikiCharacterDetail
                  character={selectedCharacter}
                  onOpenCultivation={() => openCharacterProgression(selectedCharacter)}
                  onOpenItems={() => openCharacterItems(selectedCharacter)}
                  onOpenSkills={() => openCharacterSkills(selectedCharacter)}
                  onSelectItem={openItem}
                  relatedCharacters={characters}
                  onSelectRelated={openCharacter}
                  onSelectSkill={openSkill}
                />
              ) : null}

              {page === "CharacterProgression" && selectedCharacter ? (
                <WikiCharacterProgressionPage character={selectedCharacter} />
              ) : null}

              {page === "Characters" ? (
                <WikiCharacterBrowser
                  characters={characters}
                  novel={trackedNovel}
                  onSelectCharacter={openCharacter}
                />
              ) : null}

              {page === "Skills" ? (
                <WikiSkillsIndex
                  characters={characters}
                  novel={trackedNovel}
                  onSelectCharacter={openCharacter}
                  onSelectSkill={openSkill}
                  skills={skills}
                />
              ) : null}

              {page === "Cultivation" ? (
                <WikiCultivationPage
                  characters={characters}
                  novel={trackedNovel}
                  progressionEvents={progressionEvents}
                  selectedCharacter={null}
                  onSelectCharacterProgression={openCharacterProgression}
                />
              ) : null}

              {page === "Skill" && selectedSkill ? (
                <WikiSkillPage
                  skill={selectedSkill}
                  onSelectCharacter={openCharacter}
                />
              ) : null}

              {page === "Items" ? (
                <WikiItemsIndex
                  characters={characters}
                  items={items}
                  novel={trackedNovel}
                  onSelectCharacter={openCharacter}
                  onSelectItem={openItem}
                />
              ) : null}

              {page === "Search" ? (
                <WikiSearchResultsPage
                  characters={characters}
                  items={items}
                  novel={trackedNovel}
                  skills={skills}
                  onSelectCharacter={openCharacter}
                  onSelectItem={openItem}
                  onSelectSkill={openSkill}
                />
              ) : null}

              {page === "Item" && selectedItem ? (
                <WikiItemPage
                  item={selectedItem}
                  onSelectCharacter={openCharacter}
                />
              ) : null}

              {page === "Overview" ? (
                <WikiNovelOverview
                  characters={characters}
                  items={items}
                  novel={trackedNovel}
                  onOpenCharacters={openCharacters}
                  onOpenCultivation={openCultivation}
                  onOpenItems={openItems}
                  onOpenSkills={openSkills}
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
