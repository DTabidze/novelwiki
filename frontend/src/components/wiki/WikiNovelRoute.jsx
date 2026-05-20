import React from "react";
import { useParams } from "react-router-dom";
import WikiPanel from "./WikiPanel.jsx";

export default function WikiNovelRoute({
  items,
  loading,
  loadNovel,
  loadCharacter,
  loadItem,
  loadSkill,
  novel,
  novels,
  onOpenAdmin,
  setMessage,
  ...props
}) {
  const { novelId, characterId, itemId, skillId } = useParams();
  const numericNovelId = Number(novelId);
  const numericCharacterId = characterId ? Number(characterId) : null;
  const numericSkillId = skillId ? Number(skillId) : null;
  const numericItemId = itemId ? Number(itemId) : null;
  const page =
    props.page === "CharacterProgression"
      ? "CharacterProgression"
      : numericCharacterId
        ? "Character"
        : numericSkillId
          ? "Skill"
          : numericItemId
            ? "Item"
            : props.page;

  React.useEffect(() => {
    if (numericNovelId && (!novel || novel.id !== numericNovelId)) {
      loadNovel(numericNovelId).catch((error) => setMessage(error.message));
    }
  }, [numericNovelId, novel, loadNovel, setMessage]);

  React.useEffect(() => {
    if (!numericCharacterId || props.selectedCharacter?.id === numericCharacterId) {
      return;
    }

    const listedCharacter = props.characters.find((character) => character.id === numericCharacterId);
    if (listedCharacter) {
      loadCharacter(listedCharacter).catch((error) => setMessage(error.message));
    }
  }, [numericCharacterId, props.characters, props.selectedCharacter, loadCharacter, setMessage]);

  React.useEffect(() => {
    if (!numericSkillId || props.selectedSkill?.id === numericSkillId) {
      return;
    }

    const listedSkill = props.skills.find((skill) => skill.id === numericSkillId);
    if (listedSkill) {
      loadSkill(listedSkill).catch((error) => setMessage(error.message));
    }
  }, [numericSkillId, props.skills, props.selectedSkill, loadSkill, setMessage]);

  React.useEffect(() => {
    if (!numericItemId || props.selectedItem?.id === numericItemId) {
      return;
    }

    const listedItem = items.find((item) => item.id === numericItemId);
    if (listedItem) {
      loadItem(listedItem).catch((error) => setMessage(error.message));
    }
  }, [numericItemId, items, props.selectedItem, loadItem, setMessage]);

  return (
    <WikiPanel
      {...props}
      items={items}
      loading={loading}
      novel={novel}
      novels={novels}
      onLoadNovel={loadNovel}
      onOpenAdmin={onOpenAdmin}
      onSelectCharacter={loadCharacter}
      page={page}
      progressionEvents={props.progressionEvents}
    />
  );
}
