import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import en from "../i18n/en.json";
import tr from "../i18n/tr.json";
import Hero from "./Hero";

afterEach(cleanup);

describe("Hero collection card", () => {
  it("starts the 3I/ATLAS search and links to IRSA's 3I/ATLAS page", () => {
    const onSearch = vi.fn();
    render(<Hero onSearch={onSearch} />);
    fireEvent.click(screen.getByRole("button", { name: tr.collection.atlas.play }));
    expect(onSearch).toHaveBeenCalledWith("3I/ATLAS");
    const link = screen.getByRole("link", { name: tr.collection.atlas.irsa });
    expect(link.getAttribute("href")).toBe(
      "https://irsa.ipac.caltech.edu/data/SPHEREx/docs/comet3iatlas/index.html",
    );
    expect(link.getAttribute("rel")).toContain("noopener");
  });
});

describe("i18n", () => {
  it("has the same keys in Turkish and English", () => {
    const keys = (o: object, p = ""): string[] =>
      Object.entries(o).flatMap(([k, v]) =>
        v && typeof v === "object" ? keys(v as object, `${p}${k}.`) : [`${p}${k}`],
      );
    expect(keys(en).sort()).toEqual(keys(tr).sort());
  });
});
