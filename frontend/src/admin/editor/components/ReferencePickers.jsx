import React from "react";
import { Search, X } from "lucide-react";

import { getCharacterSubtitle } from "../editorDrafts.js";

function usePickerDismiss(pickerRef, setIsOpen) {
  React.useEffect(() => {
    function handlePointerDown(event) {
      if (pickerRef.current && !pickerRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [pickerRef, setIsOpen]);
}

export function SkillReferencePicker({ availableSkills, invalid, isDuplicateSkill, onChange, value }) {
  const pickerRef = React.useRef(null);
  const selectedSkill = availableSkills.find((skill) => String(skill.id) === String(value));
  const [query, setQuery] = React.useState(selectedSkill?.name || "");
  const [isOpen, setIsOpen] = React.useState(false);

  React.useEffect(() => {
    if (value) {
      setQuery(selectedSkill?.name || "");
    }
  }, [selectedSkill?.name, value]);
  usePickerDismiss(pickerRef, setIsOpen);

  const normalizedQuery = query.trim().toLowerCase();
  const matchingSkills = availableSkills
    .filter((skill) => {
      const aliasText = (skill.aliases || []).map((alias) => alias.alias).join(" ");
      return (
        !normalizedQuery
        || skill.name?.toLowerCase().includes(normalizedQuery)
        || aliasText.toLowerCase().includes(normalizedQuery)
      );
    })
    .slice(0, 40);

  function selectSkill(skill) {
    if (isDuplicateSkill(skill.id)) {
      return;
    }

    onChange(String(skill.id), skill);
    setQuery(skill.name);
    setIsOpen(false);
  }

  return (
    <div className="editor-skill-picker" ref={pickerRef}>
      <div className={`editor-search-field ${invalid ? "editor-invalid-control" : ""}`}>
        <Search aria-hidden="true" size={16} />
        <input
          aria-label="Search and select skill"
          autoComplete="off"
          placeholder="Search skills"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setIsOpen(true);

            if (value) {
              onChange("", null);
            }
          }}
          onFocus={() => {
            setQuery("");
            setIsOpen(true);
          }}
        />
        {value ? (
          <button
            type="button"
            aria-label="Clear selected skill"
            onClick={() => {
              onChange("", null);
              setQuery("");
              setIsOpen(true);
            }}
          >
            <X aria-hidden="true" size={16} />
          </button>
        ) : null}
      </div>
      {isOpen ? (
        <div className="editor-skill-picker-results">
          {matchingSkills.length ? matchingSkills.map((skill) => {
            const isDuplicate = isDuplicateSkill(skill.id);
            return (
              <button
                type="button"
                disabled={isDuplicate}
                key={skill.id}
                onClick={() => selectSkill(skill)}
              >
                <strong>{skill.name}</strong>
                <span>{isDuplicate ? "Already attached to this character" : skill.category || "Skill"}</span>
              </button>
            );
          }) : <div className="editor-skill-picker-empty">No matching skills.</div>}
        </div>
      ) : null}
    </div>
  );
}

export function CharacterReferencePicker({ availableCharacters, invalid, isDuplicateCharacter, onChange, value }) {
  const pickerRef = React.useRef(null);
  const selectedCharacter = availableCharacters.find((character) => String(character.id) === String(value));
  const [query, setQuery] = React.useState(selectedCharacter?.name || "");
  const [isOpen, setIsOpen] = React.useState(false);

  React.useEffect(() => {
    if (value) {
      setQuery(selectedCharacter?.name || "");
    }
  }, [selectedCharacter?.name, value]);
  usePickerDismiss(pickerRef, setIsOpen);

  const normalizedQuery = query.trim().toLowerCase();
  const matchingCharacters = availableCharacters
    .filter((character) => {
      const aliasText = (character.aliases || []).map((alias) => alias.alias).join(" ");
      return (
        !normalizedQuery
        || character.name?.toLowerCase().includes(normalizedQuery)
        || aliasText.toLowerCase().includes(normalizedQuery)
      );
    })
    .slice(0, 40);

  function selectCharacter(character) {
    if (isDuplicateCharacter(character.id)) {
      return;
    }

    onChange(String(character.id), character);
    setQuery(character.name);
    setIsOpen(false);
  }

  return (
    <div className="editor-skill-picker" ref={pickerRef}>
      <div className={`editor-search-field ${invalid ? "editor-invalid-control" : ""}`}>
        <Search aria-hidden="true" size={16} />
        <input
          aria-label="Search and select character"
          autoComplete="off"
          placeholder="Search characters"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setIsOpen(true);

            if (value) {
              onChange("", null);
            }
          }}
          onFocus={() => {
            setQuery("");
            setIsOpen(true);
          }}
        />
        {value ? (
          <button
            type="button"
            aria-label="Clear selected character"
            onClick={() => {
              onChange("", null);
              setQuery("");
              setIsOpen(true);
            }}
          >
            <X aria-hidden="true" size={16} />
          </button>
        ) : null}
      </div>
      {isOpen ? (
        <div className="editor-skill-picker-results">
          {matchingCharacters.length ? matchingCharacters.map((character) => {
            const isDuplicate = isDuplicateCharacter(character.id);
            return (
              <button
                type="button"
                disabled={isDuplicate}
                key={character.id}
                onClick={() => selectCharacter(character)}
              >
                <strong>{character.name}</strong>
                <span>{isDuplicate ? "Already attached to this skill" : getCharacterSubtitle(character)}</span>
              </button>
            );
          }) : <div className="editor-skill-picker-empty">No matching characters.</div>}
        </div>
      ) : null}
    </div>
  );
}

export function ItemReferencePicker({ availableItems, invalid, isDuplicateItem, onChange, value }) {
  const pickerRef = React.useRef(null);
  const selectedItem = availableItems.find((item) => String(item.id) === String(value));
  const [query, setQuery] = React.useState(selectedItem?.name || "");
  const [isOpen, setIsOpen] = React.useState(false);

  React.useEffect(() => {
    if (value) {
      setQuery(selectedItem?.name || "");
    }
  }, [selectedItem?.name, value]);
  usePickerDismiss(pickerRef, setIsOpen);

  const normalizedQuery = query.trim().toLowerCase();
  const matchingItems = availableItems
    .filter((item) => (
      !normalizedQuery
      || item.name?.toLowerCase().includes(normalizedQuery)
    ))
    .slice(0, 40);

  function selectItem(item) {
    if (isDuplicateItem(item.id)) {
      return;
    }

    onChange(String(item.id), item);
    setQuery(item.name);
    setIsOpen(false);
  }

  return (
    <div className="editor-skill-picker" ref={pickerRef}>
      <div className={`editor-search-field ${invalid ? "editor-invalid-control" : ""}`}>
        <Search aria-hidden="true" size={16} />
        <input
          aria-label="Search and select item"
          autoComplete="off"
          placeholder="Search items"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setIsOpen(true);

            if (value) {
              onChange("", null);
            }
          }}
          onFocus={() => {
            setQuery("");
            setIsOpen(true);
          }}
        />
        {value ? (
          <button
            type="button"
            aria-label="Clear selected item"
            onClick={() => {
              onChange("", null);
              setQuery("");
              setIsOpen(true);
            }}
          >
            <X aria-hidden="true" size={16} />
          </button>
        ) : null}
      </div>
      {isOpen ? (
        <div className="editor-skill-picker-results">
          {matchingItems.length ? matchingItems.map((item) => {
            const isDuplicate = isDuplicateItem(item.id);
            return (
              <button
                type="button"
                disabled={isDuplicate}
                key={item.id}
                onClick={() => selectItem(item)}
              >
                <strong>{item.name}</strong>
                <span>{isDuplicate ? "Already attached to this character" : item.category || "Item"}</span>
              </button>
            );
          }) : <div className="editor-skill-picker-empty">No matching items.</div>}
        </div>
      ) : null}
    </div>
  );
}
