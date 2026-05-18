import React from "react";
import { useParams } from "react-router-dom";
import WikiPanel from "./WikiPanel.jsx";

export default function WikiNovelRoute({ items, loading, loadNovel, loadCharacter, novel, novels, onOpenAdmin, setMessage, ...props }) {
  const { novelId, characterId } = useParams();
  const numericNovelId = Number(novelId);
  const numericCharacterId = characterId ? Number(characterId) : null;
  const page = numericCharacterId ? "Character" : props.page;

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
    />
  );
}
