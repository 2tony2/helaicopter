import { stat } from "fs/promises";

interface CacheEntry<T> {
  data: T;
  mtime: number;
  accessedAt: number;
}

/**
 * In-memory LRU cache keyed on file path + mtime.
 * Automatically invalidates when the file changes.
 */
export class FileCache<T> {
  private cache = new Map<string, CacheEntry<T>>();
  private maxSize: number;

  constructor(maxSize = 50) {
    this.maxSize = maxSize;
  }

  async get(filePath: string): Promise<T | null> {
    const entry = this.cache.get(filePath);
    if (!entry) return null;

    try {
      const stats = await stat(filePath);
      const mtime = stats.mtimeMs;
      if (mtime !== entry.mtime) {
        this.cache.delete(filePath);
        return null;
      }
      entry.accessedAt = Date.now();
      return entry.data;
    } catch {
      this.cache.delete(filePath);
      return null;
    }
  }

  async set(filePath: string, data: T): Promise<void> {
    // Evict oldest if at capacity
    if (this.cache.size >= this.maxSize) {
      let oldestKey: string | null = null;
      let oldestTime = Infinity;
      for (const [key, entry] of this.cache) {
        if (entry.accessedAt < oldestTime) {
          oldestTime = entry.accessedAt;
          oldestKey = key;
        }
      }
      if (oldestKey) this.cache.delete(oldestKey);
    }

    try {
      const stats = await stat(filePath);
      this.cache.set(filePath, {
        data,
        mtime: stats.mtimeMs,
        accessedAt: Date.now(),
      });
    } catch {
      // Can't stat file, don't cache
    }
  }
}

// Singleton caches for different data types
export const summaryCache = new FileCache<unknown>(100);
export const conversationCache = new FileCache<unknown>(20);
