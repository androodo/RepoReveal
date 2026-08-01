import { z } from "zod";

const OWNER_RE = /^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$/;
const REPO_RE = /^[A-Za-z0-9._-]{1,100}$/;
const GITHUB_HTTPS_RE = /^https:\/\/github\.com\/([^/]+)\/([^/?#]+?)(?:\.git)?\/?$/;

export const githubUrlSchema = z
  .string()
  .trim()
  .min(1, "Repository URL is required.")
  .superRefine((value, ctx) => {
    const lower = value.toLowerCase();
    if (lower.startsWith("git@")) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "SSH URLs are not supported. Use https://github.com/owner/repo.",
      });
      return;
    }
    if (!lower.includes("github.com")) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Only github.com repository URLs are supported.",
      });
      return;
    }
    if (
      ["/issues", "/pull/", "/pulls", "/blob/", "/tree/", "/commit/", "/raw/"].some((m) =>
        lower.includes(m),
      )
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Provide a repository root URL, not an issue, pull request, or file URL.",
      });
      return;
    }
    const match = GITHUB_HTTPS_RE.exec(value);
    if (!match) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Invalid GitHub URL. Expected https://github.com/owner/repository.",
      });
      return;
    }
    const owner = match[1];
    let repo = match[2];
    if (repo.endsWith(".git")) repo = repo.slice(0, -4);
    if (!OWNER_RE.test(owner)) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Invalid GitHub owner name." });
      return;
    }
    if (!REPO_RE.test(repo) || repo === "." || repo === "..") {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Invalid GitHub repository name." });
    }
  });

export function normalizeGithubUrl(value: string): string {
  const match = GITHUB_HTTPS_RE.exec(value.trim());
  if (!match) return value.trim();
  let repo = match[2];
  if (repo.endsWith(".git")) repo = repo.slice(0, -4);
  return `${match[1]}/${repo}`;
}

export function parseGithubUrl(value: string): { owner: string; name: string } | null {
  const parsed = githubUrlSchema.safeParse(value);
  if (!parsed.success) return null;
  const match = GITHUB_HTTPS_RE.exec(value.trim());
  if (!match) return null;
  let repo = match[2];
  if (repo.endsWith(".git")) repo = repo.slice(0, -4);
  return { owner: match[1], name: repo };
}
