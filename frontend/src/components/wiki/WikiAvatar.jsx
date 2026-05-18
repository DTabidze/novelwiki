import React from "react";
import { initialsForName } from "../../utils/wikiFormat.js";

export default function WikiAvatar({ name, size = "large" }) {
  return (
    <div className={`wiki-avatar ${size}`} aria-hidden="true">
      <span>{initialsForName(name)}</span>
    </div>
  );
}
