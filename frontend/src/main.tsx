import "@fontsource-variable/inter";
import "@fontsource-variable/exo-2";
import "@fontsource/roboto-mono/400.css";
import "./styles.css";
import "./i18n";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
