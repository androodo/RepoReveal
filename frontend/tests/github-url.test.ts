import { describe, expect, it } from "vitest";
import { githubUrlSchema, normalizeGithubUrl, parseGithubUrl } from "@/lib/github-url";

describe("github url validation", () => {
  it("accepts and normalizes valid urls", () => {
    expect(normalizeGithubUrl("https://github.com/owner/repository.git")).toBe(
      "owner/repository",
    );
    expect(parseGithubUrl("https://github.com/owner/repository/")).toEqual({
      owner: "owner",
      name: "repository",
    });
    expect(githubUrlSchema.safeParse("https://github.com/owner/repository").success).toBe(true);
  });

  it("rejects invalid urls", () => {
    expect(githubUrlSchema.safeParse("https://gitlab.com/a/b").success).toBe(false);
    expect(githubUrlSchema.safeParse("git@github.com:a/b.git").success).toBe(false);
    expect(githubUrlSchema.safeParse("https://github.com/a/b/issues/1").success).toBe(false);
  });
});
