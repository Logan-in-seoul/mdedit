import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { OutlineSidebar } from "./components/OutlineSidebar";
import "./styles/global.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// Mount OutlineSidebar as an independent root so we don't have to thread props
// through App.tsx. The outline panel reads the active note's headings directly
// from the rendered DOM via MutationObserver.
const outlineHost = document.createElement("div");
outlineHost.id = "outline-host";
document.body.appendChild(outlineHost);
ReactDOM.createRoot(outlineHost).render(
  <React.StrictMode>
    <OutlineSidebar />
  </React.StrictMode>,
);
