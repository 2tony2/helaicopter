import { stat } from "fs/promises";

interface CacheEntry<T> {
  data: T;
  mtime: number;
  accessedAt: number;
}

interface TtlCacheEntry<T> {
  data: T;
  expiresAt: number;
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

export class TtlCache<T> {
  private cache = new Map<string, TtlCacheEntry<T>>();
  private inFlight = new Map<string, Promise<T>>();
  private maxSize: number;

  constructor(maxSize = 50) {
    this.maxSize = maxSize;
  }

  get(key: string): T | null {
    const entry = this.cache.get(key);
    if (!entry) return null;

    if (entry.expiresAt <= Date.now()) {
      this.cache.delete(key);
      return null;
    }

    entry.accessedAt = Date.now();
    return entry.data;
  }

  async getOrLoad(
    key: string,
    ttlMs: number,
    loader: () => Promise<T>
  ): Promise<T> {
    const cached = this.get(key);
    if (cached !== null) {
      return cached;
    }

    const existingLoad = this.inFlight.get(key);
    if (existingLoad) {
      return existingLoad;
    }

    const loadPromise = loader()
      .then((data) => {
        this.set(key, data, ttlMs);
        return data;
      })
      .finally(() => {
        this.inFlight.delete(key);
      });

    this.inFlight.set(key, loadPromise);
    return loadPromise;
  }

  set(key: string, data: T, ttlMs: number): void {
    if (this.cache.size >= this.maxSize) {
      let oldestKey: string | null = null;
      let oldestTime = Infinity;
      for (const [candidateKey, entry] of this.cache) {
        if (entry.accessedAt < oldestTime) {
          oldestTime = entry.accessedAt;
          oldestKey = candidateKey;
        }
      }
      if (oldestKey) this.cache.delete(oldestKey);
    }

    this.cache.set(key, {
      data,
      expiresAt: Date.now() + ttlMs,
      accessedAt: Date.now(),
    });
  }

  clear(): void {
    this.cache.clear();
    this.inFlight.clear();
  }
}

// Singleton caches for different data types
export const summaryCache = new FileCache<unknown>(100);
export const conversationCache = new FileCache<unknown>(20);
export const analyticsResponseCache = new TtlCache<unknown>(24);
export const conversationListResponseCache = new TtlCache<unknown>(24);
export const projectListResponseCache = new TtlCache<unknown>(8);

export function clearExpensiveReadCaches(): void {
  analyticsResponseCache.clear();
  conversationListResponseCache.clear();
  projectListResponseCache.clear();
}
