const DAY_MS = 24 * 60 * 60 * 1000;

export function startOfToday(): Date {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

export function startOfTodayMs(): number {
  return startOfToday().getTime();
}

export function startOfTodayIso(): string {
  return startOfToday().toISOString();
}

export function daysAgoIso(days: number): string {
  return new Date(Date.now() - days * DAY_MS).toISOString();
}

export function isTimestampToday(timestamp: number): boolean {
  return Number.isFinite(timestamp) && timestamp >= startOfTodayMs();
}
