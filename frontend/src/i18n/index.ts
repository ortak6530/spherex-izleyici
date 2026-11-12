import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import { storage } from "../lib/storage";
import en from "./en.json";
import tr from "./tr.json";

export const LANGS = ["tr", "en"] as const;
export type Lang = (typeof LANGS)[number];

const saved = storage.get("lang");
const initial: Lang = saved === "en" ? "en" : "tr"; // Turkish is the default UI language

void i18n.use(initReactI18next).init({
  resources: { tr: { translation: tr }, en: { translation: en } },
  lng: initial,
  fallbackLng: "tr",
  interpolation: { escapeValue: false }, // React already escapes
});

export function setLang(lang: Lang) {
  void i18n.changeLanguage(lang);
  storage.set("lang", lang);
  document.documentElement.lang = lang;
}

document.documentElement.lang = initial;
export default i18n;
