import React from "react";
import { Search, X } from "lucide-react";

import { API_BASE_URL, fetchJson } from "../../../api.js";
import { cleanChapterTitle } from "../../../utils/wikiFormat.js";
import { formatChapter } from "../editorDrafts.js";

const chapterLookupCache = new Map();

function chapterInputLabel(chapter) {
  return chapter ? formatChapter(chapter) : "";
}

function compactChapterInputLabel(chapter) {
  const label = chapterInputLabel(chapter);
  return label.length > 52 ? `${label.slice(0, 52)}...` : label;
}

async function fetchChapterLookup(novelId, params) {
  const query = new URLSearchParams(params);
  const cacheKey = `${novelId}?${query.toString()}`;

  if (!chapterLookupCache.has(cacheKey)) {
    const request = fetchJson(`${API_BASE_URL}/admin/review/wiki-data/novels/${novelId}/chapters/search?${query.toString()}`)
      .catch((error) => {
        chapterLookupCache.delete(cacheKey);
        throw error;
      });

    chapterLookupCache.set(cacheKey, request);
  }

  return chapterLookupCache.get(cacheKey);
}

export default function ChapterReferencePicker({
  className = "",
  evidenceChapterId,
  label,
  novelId,
  onChange,
  onValidationChange,
  placeholder = "Chapter number",
  value,
}) {
  const [chapterNumber, setChapterNumber] = React.useState("");
  const [selectedChapter, setSelectedChapter] = React.useState(null);
  const [searchText, setSearchText] = React.useState("");
  const [searchResults, setSearchResults] = React.useState([]);
  const [isSearching, setIsSearching] = React.useState(false);
  const [pickerError, setPickerError] = React.useState("");
  const onValidationChangeRef = React.useRef(onValidationChange);
  const lastValidityRef = React.useRef(null);
  const pickerRef = React.useRef(null);

  React.useEffect(() => {
    onValidationChangeRef.current = onValidationChange;
  }, [onValidationChange]);

  const reportValidity = React.useCallback((isValid) => {
    if (lastValidityRef.current === isValid) {
      return;
    }

    lastValidityRef.current = isValid;
    onValidationChangeRef.current?.(isValid);
  }, []);

  async function lookupChapter(params) {
    if (!novelId) {
      return null;
    }

    const data = await fetchChapterLookup(novelId, params);
    return data.chapters?.[0] || null;
  }

  async function selectChapter(chapter) {
    if (!chapter) {
      setSelectedChapter(null);
      setChapterNumber("");
      setPickerError("");
      reportValidity(true);
      onChange("", null);
      return;
    }

    setSelectedChapter(chapter);
    setChapterNumber(String(chapter.chapter_number));
    setPickerError("");
    setSearchText("");
    setSearchResults([]);
    reportValidity(true);
    onChange(String(chapter.id), chapter);
  }

  function closeSearchResults() {
    setSearchText("");
    setSearchResults([]);
  }

  React.useEffect(() => {
    let isActive = true;

    async function loadSelectedChapter() {
      if (!value) {
        setSelectedChapter(null);
        setChapterNumber("");
        setPickerError("");
        reportValidity(true);
        return;
      }

      try {
        const chapter = await lookupChapter({ chapter_id: value });

        if (!isActive) {
          return;
        }

        if (chapter) {
          setSelectedChapter(chapter);
          setChapterNumber(String(chapter.chapter_number));
          setPickerError("");
          reportValidity(true);
        } else {
          setSelectedChapter(null);
          setPickerError("Saved chapter reference could not be found for this novel.");
          reportValidity(false);
        }
      } catch (error) {
        if (isActive) {
          setPickerError(error.message);
          reportValidity(false);
        }
      }
    }

    loadSelectedChapter();

    return () => {
      isActive = false;
    };
  }, [value, novelId, reportValidity]);

  React.useEffect(() => {
    const query = searchText.trim();

    if (!query || query.length < 2) {
      setSearchResults([]);
      return undefined;
    }

    let isActive = true;
    const timeoutId = window.setTimeout(async () => {
      setIsSearching(true);
      try {
        const data = await fetchJson(`${API_BASE_URL}/admin/review/wiki-data/novels/${novelId}/chapters/search?q=${encodeURIComponent(query)}`);

        if (isActive) {
          setSearchResults(data.chapters || []);
        }
      } catch (error) {
        if (isActive) {
          setPickerError(error.message);
        }
      } finally {
        if (isActive) {
          setIsSearching(false);
        }
      }
    }, 250);

    return () => {
      isActive = false;
      window.clearTimeout(timeoutId);
    };
  }, [searchText, novelId]);

  React.useEffect(() => {
    function handleDocumentPointerDown(event) {
      if (pickerRef.current && !pickerRef.current.contains(event.target)) {
        closeSearchResults();
      }
    }

    function handleDocumentKeyDown(event) {
      if (event.key === "Escape") {
        closeSearchResults();
      }
    }

    document.addEventListener("pointerdown", handleDocumentPointerDown);
    document.addEventListener("keydown", handleDocumentKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handleDocumentPointerDown);
      document.removeEventListener("keydown", handleDocumentKeyDown);
    };
  }, []);

  async function resolveChapterNumber() {
    const normalizedNumber = String(chapterNumber || "").trim();

    if (!normalizedNumber) {
      await selectChapter(null);
      return;
    }

    const numericChapter = Number(normalizedNumber);

    if (!Number.isInteger(numericChapter) || numericChapter <= 0) {
      setPickerError("Enter a valid chapter number.");
      reportValidity(false);
      return;
    }

    try {
      const chapter = await lookupChapter({ number: numericChapter });

      if (!chapter) {
        setSelectedChapter(null);
        setPickerError(`Chapter ${numericChapter} does not exist for this novel.`);
        reportValidity(false);
        return;
      }

      await selectChapter(chapter);
    } catch (error) {
      setPickerError(error.message);
      reportValidity(false);
    }
  }

  async function useEvidenceChapter() {
    if (!evidenceChapterId) {
      return;
    }

    try {
      const chapter = await lookupChapter({ chapter_id: evidenceChapterId });

      if (!chapter) {
        setPickerError("Evidence chapter could not be found.");
        reportValidity(false);
        return;
      }

      await selectChapter(chapter);
    } catch (error) {
      setPickerError(error.message);
      reportValidity(false);
    }
  }

  return (
    <div className={`chapter-reference-picker ${className}`} ref={pickerRef}>
      <div className="chapter-reference-input-row">
        <div className="chapter-reference-value-field">
          <input
            inputMode={selectedChapter ? "text" : "numeric"}
            placeholder={placeholder}
            title={selectedChapter ? chapterInputLabel(selectedChapter) : ""}
            value={selectedChapter && chapterNumber === String(selectedChapter.chapter_number) ? compactChapterInputLabel(selectedChapter) : chapterNumber}
            onFocus={() => {
              if (selectedChapter) {
                setChapterNumber(String(selectedChapter.chapter_number));
              }
            }}
            onBlur={resolveChapterNumber}
            onChange={(event) => {
              setSelectedChapter(null);
              setChapterNumber(event.target.value);
              setPickerError("");
              reportValidity(false);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                resolveChapterNumber();
              }
            }}
          />
          {value ? (
            <button type="button" className="chapter-reference-clear" onClick={() => selectChapter(null)} aria-label={`Clear ${label}`}>
              <X aria-hidden="true" size={16} />
            </button>
          ) : null}
        </div>
      </div>

      {pickerError ? <div className="chapter-reference-error">{pickerError}</div> : null}

      <div className="chapter-reference-search">
        <div className="editor-search-field compact">
          <Search aria-hidden="true" size={15} />
          <input
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
            placeholder="Search chapters"
          />
        </div>
        {evidenceChapterId ? (
          <button type="button" className="admin-secondary-button" onClick={useEvidenceChapter}>
            Use evidence chapter
          </button>
        ) : null}
      </div>

      {searchResults.length ? (
        <div className="chapter-reference-results">
          {searchResults.map((chapter) => (
            <button type="button" key={chapter.id} onClick={() => selectChapter(chapter)}>
              <strong>Chapter {chapter.chapter_number}</strong>
              <span>{cleanChapterTitle(chapter) || chapter.title}</span>
              {chapter.book ? <small>Book {chapter.book.number}: {chapter.book.title}</small> : null}
            </button>
          ))}
        </div>
      ) : searchText.trim().length >= 2 && !isSearching ? (
        <div className="chapter-reference-no-results">No matching chapters.</div>
      ) : null}
    </div>
  );
}
