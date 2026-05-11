import React from "react";
import { createRoot } from "react-dom/client";

function App() {
  return (
    <main>
      <h1>NovelWiki</h1>
      <p>Starter scaffold for the novel wiki MVP.</p>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);

