import { describe, expect, it } from "vitest";
import { isHttpUrl } from "./url";

describe("isHttpUrl", () => {
  it.each(["https://x.example/a", "http://x.example"])("accepts %s", (url) => {
    expect(isHttpUrl(url)).toBe(true);
  });
  it.each(["javascript:alert(1)", "data:text/html,x", "ftp://x", "not a url", ""])(
    "rejects %s",
    (url) => {
      expect(isHttpUrl(url)).toBe(false);
    },
  );
});
