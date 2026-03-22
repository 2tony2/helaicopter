import fs from "node:fs";
import path from "node:path";

export interface AppDocEntry {
  slug: string[];
  href: string;
  title: string;
  description?: string;
}

export interface AppDocPage extends AppDocEntry {
  body: string;
}

interface DocManifestEntry extends AppDocEntry {
  absolutePath: string;
}

const DOCS_ROOT = path.join(process.cwd(), "docs");

function stripMdxExtension(value: string): string {
  return value.replace(/\.(md|mdx)$/i, "");
}

function titleFromSlug(slug: string[]): string {
  const value = slug[slug.length - 1] ?? "docs";
  return value
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function parseFrontmatter(raw: string): { title?: string; description?: string; body: string } {
  if (!raw.startsWith("---\n")) {
    return { body: raw };
  }

  const end = raw.indexOf("\n---\n", 4);
  if (end === -1) {
    return { body: raw };
  }

  const frontmatter = raw.slice(4, end);
  const body = raw.slice(end + 5);
  const title = frontmatter.match(/^title:\s*(.+)$/m)?.[1]?.trim();
  const description = frontmatter.match(/^description:\s*(.+)$/m)?.[1]?.trim();
  return {
    title: title?.replace(/^['"]|['"]$/g, ""),
    description: description?.replace(/^['"]|['"]$/g, ""),
    body,
  };
}

function docsManifest(): DocManifestEntry[] {
  const entries: DocManifestEntry[] = [];
  const pending = [DOCS_ROOT];

  while (pending.length > 0) {
    const current = pending.pop();
    if (!current) continue;
    for (const dirent of fs.readdirSync(current, { withFileTypes: true })) {
      const absolutePath = path.join(current, dirent.name);
      if (dirent.isDirectory()) {
        pending.push(absolutePath);
        continue;
      }
      if (!/\.(md|mdx)$/i.test(dirent.name)) {
        continue;
      }
      const relativePath = path.relative(DOCS_ROOT, absolutePath);
      const slug = stripMdxExtension(relativePath).split(path.sep);
      const raw = fs.readFileSync(absolutePath, "utf-8");
      const parsed = parseFrontmatter(raw);
      entries.push({
        slug,
        href: `/docs/${slug.join("/")}`.replace(/\/index$/, ""),
        title: parsed.title ?? titleFromSlug(slug),
        description: parsed.description,
        absolutePath,
      });
    }
  }

  return entries.sort((left, right) => left.href.localeCompare(right.href));
}

export function getAppDocsNavigation(): AppDocEntry[] {
  return docsManifest().map((entry) => ({
    slug: entry.slug,
    href: entry.href,
    title: entry.title,
    description: entry.description,
  }));
}

export function loadAppDoc(slug: string[] = []): AppDocPage | null {
  const normalized = slug.length === 0 ? ["index"] : slug;
  const match = docsManifest().find(
    (entry) => entry.slug.join("/") === normalized.join("/")
  );
  if (!match) {
    return null;
  }
  const raw = fs.readFileSync(match.absolutePath, "utf-8");
  const parsed = parseFrontmatter(raw);
  const isIndex = normalized.length === 1 && normalized[0] === "index";
  return {
    slug: match.slug,
    href: match.href,
    title: isIndex ? "Helaicopter Platform Documentation" : (parsed.title ?? match.title),
    description: parsed.description ?? match.description,
    body: parsed.body,
  };

}
