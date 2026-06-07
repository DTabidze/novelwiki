import React from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { API_BASE_URL, fetchJson } from "./api.js";
import AdminApp from "./admin/AdminApp.jsx";
import WikiPanel from "./components/wiki/WikiPanel.jsx";
import WikiNovelRoute from "./components/wiki/WikiNovelRoute.jsx";

function PublicWikiScrollReset() {
  const location = useLocation();

  React.useEffect(() => {
    if (!location.pathname.startsWith("/wiki")) {
      return;
    }

    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  }, [location.pathname]);

  return null;
}

export default function App() {
  const navigate = useNavigate();
  const [message, setMessage] = React.useState("");
  const [wikiCharacters, setWikiCharacters] = React.useState([]);
  const [wikiItems, setWikiItems] = React.useState([]);
  const [wikiLoading, setWikiLoading] = React.useState(false);
  const [wikiNovel, setWikiNovel] = React.useState(null);
  const [wikiNovels, setWikiNovels] = React.useState([]);
  const [wikiProgressionEvents, setWikiProgressionEvents] = React.useState([]);
  const [wikiSelectedCharacter, setWikiSelectedCharacter] = React.useState(null);
  const [wikiSelectedItem, setWikiSelectedItem] = React.useState(null);
  const [wikiSelectedNovelId, setWikiSelectedNovelId] = React.useState(null);
  const [wikiSelectedSkill, setWikiSelectedSkill] = React.useState(null);
  const [wikiSkills, setWikiSkills] = React.useState([]);

  async function loadWikiNovels() {
    const data = await fetchJson(`${API_BASE_URL}/wiki/novels`);
    setWikiNovels(data);
  }

  async function loadWikiNovel(novelId) {
    setWikiLoading(true);
    setWikiSelectedNovelId(novelId);
    setWikiSelectedCharacter(null);
    setWikiSelectedSkill(null);
    setWikiSelectedItem(null);

    try {
      const [novelData, charactersData, skillsData, itemsData, progressionData] = await Promise.all([
        fetchJson(`${API_BASE_URL}/wiki/novels/${novelId}`),
        fetchJson(`${API_BASE_URL}/wiki/novels/${novelId}/characters`),
        fetchJson(`${API_BASE_URL}/wiki/novels/${novelId}/skills`),
        fetchJson(`${API_BASE_URL}/wiki/novels/${novelId}/items`),
        fetchJson(`${API_BASE_URL}/wiki/novels/${novelId}/progression`),
      ]);

      setWikiNovel(novelData);
      setWikiCharacters(charactersData);
      setWikiSkills(skillsData);
      setWikiItems(itemsData);
      setWikiProgressionEvents(progressionData);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setWikiLoading(false);
    }
  }

  async function loadWikiCharacter(character) {
    setWikiLoading(true);

    try {
      const data = await fetchJson(`${API_BASE_URL}/wiki/characters/${character.id}`);
      setWikiSelectedCharacter(data);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setWikiLoading(false);
    }
  }

  async function loadWikiSkill(skill) {
    setWikiLoading(true);

    try {
      const data = await fetchJson(`${API_BASE_URL}/wiki/skills/${skill.id}`);
      setWikiSelectedSkill(data);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setWikiLoading(false);
    }
  }

  async function loadWikiItem(item) {
    setWikiLoading(true);

    try {
      const data = await fetchJson(`${API_BASE_URL}/wiki/items/${item.id}`);
      setWikiSelectedItem(data);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setWikiLoading(false);
    }
  }

  React.useEffect(() => {
    loadWikiNovels().catch((error) => setMessage(error.message));
  }, []);

  return (
    <>
      <PublicWikiScrollReset />
      {message ? <p className="message">{message}</p> : null}
      <Routes>
        <Route path="/" element={<Navigate to="/wiki/novels" replace />} />
        <Route path="/admin/*" element={<AdminApp />} />
        <Route path="/wiki" element={<Navigate to="/wiki/novels" replace />} />
        <Route
          path="/wiki/novels"
          element={
            <WikiPanel
              characters={[]}
              items={[]}
              loading={wikiLoading}
              novel={null}
              novels={wikiNovels}
              onLoadNovel={loadWikiNovel}
              onOpenAdmin={() => navigate("/admin")}
              onSelectCharacter={loadWikiCharacter}
              page="Novels"
              progressionEvents={[]}
              selectedCharacter={null}
              selectedItem={null}
              selectedNovelId={null}
              selectedSkill={null}
              skills={[]}
            />
          }
        />
        <Route
          path="/wiki/novels/:novelId"
          element={
            <WikiNovelRoute
              characters={wikiCharacters}
              items={wikiItems}
              loadCharacter={loadWikiCharacter}
              loadItem={loadWikiItem}
              loadSkill={loadWikiSkill}
              loading={wikiLoading}
              loadNovel={loadWikiNovel}
              novel={wikiNovel}
              novels={wikiNovels}
              onOpenAdmin={() => navigate("/admin")}
              page="Overview"
              progressionEvents={wikiProgressionEvents}
              selectedCharacter={null}
              selectedItem={null}
              selectedNovelId={wikiSelectedNovelId}
              selectedSkill={null}
              setMessage={setMessage}
              skills={wikiSkills}
            />
          }
        />
        <Route
          path="/wiki/novels/:novelId/characters"
          element={
            <WikiNovelRoute
              characters={wikiCharacters}
              items={wikiItems}
              loadCharacter={loadWikiCharacter}
              loadItem={loadWikiItem}
              loadSkill={loadWikiSkill}
              loading={wikiLoading}
              loadNovel={loadWikiNovel}
              novel={wikiNovel}
              novels={wikiNovels}
              onOpenAdmin={() => navigate("/admin")}
              page="Characters"
              progressionEvents={wikiProgressionEvents}
              selectedCharacter={null}
              selectedItem={null}
              selectedNovelId={wikiSelectedNovelId}
              selectedSkill={null}
              setMessage={setMessage}
              skills={wikiSkills}
            />
          }
        />
        <Route
          path="/wiki/novels/:novelId/characters/:characterId"
          element={
            <WikiNovelRoute
              characters={wikiCharacters}
              items={wikiItems}
              loadCharacter={loadWikiCharacter}
              loadItem={loadWikiItem}
              loadSkill={loadWikiSkill}
              loading={wikiLoading}
              loadNovel={loadWikiNovel}
              novel={wikiNovel}
              novels={wikiNovels}
              onOpenAdmin={() => navigate("/admin")}
              page="Characters"
              progressionEvents={wikiProgressionEvents}
              selectedCharacter={wikiSelectedCharacter}
              selectedItem={null}
              selectedNovelId={wikiSelectedNovelId}
              selectedSkill={null}
              setMessage={setMessage}
              skills={wikiSkills}
            />
          }
        />
        <Route
          path="/wiki/novels/:novelId/characters/:characterId/progression"
          element={
            <WikiNovelRoute
              characters={wikiCharacters}
              items={wikiItems}
              loadCharacter={loadWikiCharacter}
              loadItem={loadWikiItem}
              loadSkill={loadWikiSkill}
              loading={wikiLoading}
              loadNovel={loadWikiNovel}
              novel={wikiNovel}
              novels={wikiNovels}
              onOpenAdmin={() => navigate("/admin")}
              page="CharacterProgression"
              progressionEvents={wikiProgressionEvents}
              selectedCharacter={wikiSelectedCharacter}
              selectedItem={null}
              selectedNovelId={wikiSelectedNovelId}
              selectedSkill={null}
              setMessage={setMessage}
              skills={wikiSkills}
            />
          }
        />
        <Route
          path="/wiki/novels/:novelId/cultivation"
          element={
            <WikiNovelRoute
              characters={wikiCharacters}
              items={wikiItems}
              loadCharacter={loadWikiCharacter}
              loadItem={loadWikiItem}
              loadSkill={loadWikiSkill}
              loading={wikiLoading}
              loadNovel={loadWikiNovel}
              novel={wikiNovel}
              novels={wikiNovels}
              onOpenAdmin={() => navigate("/admin")}
              page="Cultivation"
              progressionEvents={wikiProgressionEvents}
              selectedCharacter={null}
              selectedItem={null}
              selectedNovelId={wikiSelectedNovelId}
              selectedSkill={null}
              setMessage={setMessage}
              skills={wikiSkills}
            />
          }
        />
        <Route
          path="/wiki/novels/:novelId/skills"
          element={
            <WikiNovelRoute
              characters={wikiCharacters}
              items={wikiItems}
              loadCharacter={loadWikiCharacter}
              loadItem={loadWikiItem}
              loadSkill={loadWikiSkill}
              loading={wikiLoading}
              loadNovel={loadWikiNovel}
              novel={wikiNovel}
              novels={wikiNovels}
              onOpenAdmin={() => navigate("/admin")}
              page="Skills"
              progressionEvents={wikiProgressionEvents}
              selectedCharacter={null}
              selectedItem={null}
              selectedNovelId={wikiSelectedNovelId}
              selectedSkill={null}
              setMessage={setMessage}
              skills={wikiSkills}
            />
          }
        />
        <Route
          path="/wiki/novels/:novelId/skills/:skillId"
          element={
            <WikiNovelRoute
              characters={wikiCharacters}
              items={wikiItems}
              loadCharacter={loadWikiCharacter}
              loadItem={loadWikiItem}
              loadSkill={loadWikiSkill}
              loading={wikiLoading}
              loadNovel={loadWikiNovel}
              novel={wikiNovel}
              novels={wikiNovels}
              onOpenAdmin={() => navigate("/admin")}
              page="Skills"
              progressionEvents={wikiProgressionEvents}
              selectedCharacter={null}
              selectedItem={null}
              selectedNovelId={wikiSelectedNovelId}
              selectedSkill={wikiSelectedSkill}
              setMessage={setMessage}
              skills={wikiSkills}
            />
          }
        />
        <Route
          path="/wiki/novels/:novelId/items"
          element={
            <WikiNovelRoute
              characters={wikiCharacters}
              items={wikiItems}
              loadCharacter={loadWikiCharacter}
              loadItem={loadWikiItem}
              loadSkill={loadWikiSkill}
              loading={wikiLoading}
              loadNovel={loadWikiNovel}
              novel={wikiNovel}
              novels={wikiNovels}
              onOpenAdmin={() => navigate("/admin")}
              page="Items"
              progressionEvents={wikiProgressionEvents}
              selectedCharacter={null}
              selectedItem={null}
              selectedNovelId={wikiSelectedNovelId}
              selectedSkill={null}
              setMessage={setMessage}
              skills={wikiSkills}
            />
          }
        />
        <Route
          path="/wiki/novels/:novelId/items/:itemId"
          element={
            <WikiNovelRoute
              characters={wikiCharacters}
              items={wikiItems}
              loadCharacter={loadWikiCharacter}
              loadItem={loadWikiItem}
              loadSkill={loadWikiSkill}
              loading={wikiLoading}
              loadNovel={loadWikiNovel}
              novel={wikiNovel}
              novels={wikiNovels}
              onOpenAdmin={() => navigate("/admin")}
              page="Items"
              progressionEvents={wikiProgressionEvents}
              selectedCharacter={null}
              selectedItem={wikiSelectedItem}
              selectedNovelId={wikiSelectedNovelId}
              selectedSkill={null}
              setMessage={setMessage}
              skills={wikiSkills}
            />
          }
        />
      </Routes>
    </>
  );
}
