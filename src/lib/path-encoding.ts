/**
 * Encode a project directory name for use in URL paths.
 * The project directories in ~/.claude/projects/ use dashes for slashes,
 * e.g. "-Users-tony-Documents-project" for "/Users/tony/Documents/project"
 */
export function encodeProjectPath(dirName: string): string {
  return encodeURIComponent(dirName);
}

export function decodeProjectPath(encoded: string): string {
  return decodeURIComponent(encoded);
}

/**
 * Convert a project directory name back to a readable filesystem path.
 * e.g. "-Users-tony-Documents-curadev-dbt-worktree" → "/Users/tony/Documents/curadev/dbt-worktree"
 */
export function projectDirToDisplayName(dirName: string): string {
  if (dirName.startsWith("codex:")) {
    const stripped = dirName.slice("codex:".length);
    return `Codex/${projectDirToDisplayName(stripped)}`;
  }

  // The directory name starts with "-" and uses "-" as separator
  // But some path components legitimately contain dashes
  // Best heuristic: replace leading dash, show last 2-3 meaningful segments
  if (dirName.startsWith("-")) {
    const fullPath = dirName.replace(/^-/, "/").replace(/-/g, "/");
    // Return last meaningful segments
    const segments = fullPath.split("/").filter(Boolean);
    // Skip "Users/<username>/Documents" prefix if present
    const startIdx = segments.findIndex(
      (s, i) => i >= 2 && s !== "Documents" && s !== "Users"
    );
    const meaningful = segments.slice(Math.max(startIdx, 0));
    return meaningful.slice(-3).join("/");
  }
  return dirName;
}

/**
 * Get a short display name for a project path
 */
export function shortProjectName(dirName: string): string {
  const parts = dirName.replace(/^-/, "").split("-");
  // Return last 2-4 segments
  return parts.slice(-4).join("-");
}
