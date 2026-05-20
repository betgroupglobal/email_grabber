/**
 * Engagement manager — in-memory cache with Postgres persistence (payload JSONB).
 */

const EngagementStore = require("./engagement-store");

const PERSIST_DEBOUNCE_MS = parseInt(process.env.ENGAGEMENT_PERSIST_MS || "400", 10);

class EngagementManager {
  constructor() {
    this.store = new EngagementStore();
    this.cache = new Map();
    this.initialized = false;
    this._persistTimers = new Map();
    this._persistPending = new Map();
  }

  async initialize() {
    if (this.initialized) return;

    await this.store.ready;
    const existing = await this.store.listEngagements({ limit: 5000 });
    for (const engagement of existing) {
      if (engagement?.id) this.cache.set(engagement.id, engagement);
    }
    console.log(`[engagement-manager] Loaded ${existing.length} engagement(s) from Postgres`);
    this.initialized = true;
  }

  set(key, value) {
    const id = String(key);
    const engagement = { ...value, id: value?.id || id };
    this.cache.set(id, engagement);
    this.schedulePersist(id, engagement, { immediate: true });
    return this;
  }

  get(key) {
    return this.cache.get(String(key));
  }

  has(key) {
    return this.cache.has(String(key));
  }

  delete(key) {
    const id = String(key);
    this.cache.delete(id);
    this._clearPersistTimer(id);
    this.store.deleteEngagement(id).catch((err) => {
      console.error(`[engagement-manager] Failed to delete engagement ${id}:`, err.message);
    });
    return true;
  }

  clear() {
    const keys = [...this.cache.keys()];
    this.cache.clear();
    for (const id of keys) this._clearPersistTimer(id);
    Promise.all(keys.map((id) => this.store.deleteEngagement(id))).catch((err) => {
      console.error("[engagement-manager] Failed to clear engagements:", err.message);
    });
  }

  get size() {
    return this.cache.size;
  }

  forEach(callback) {
    this.cache.forEach(callback);
  }

  keys() {
    return this.cache.keys();
  }

  values() {
    return this.cache.values();
  }

  entries() {
    return this.cache.entries();
  }

  [Symbol.iterator]() {
    return this.cache[Symbol.iterator]();
  }

  /**
   * Debounced upsert after in-memory mutations (e.g. pipeline / execute-chain).
   */
  schedulePersist(engagementId, engagement, options = {}) {
    const id = String(engagementId);
    if (engagement) this.cache.set(id, engagement);

    if (options.immediate) {
      this._clearPersistTimer(id);
      return this._flushPersist(id);
    }

    this._persistPending.set(id, true);
    if (this._persistTimers.has(id)) return;

    const timer = setTimeout(() => {
      this._persistTimers.delete(id);
      this._persistPending.delete(id);
      this._flushPersist(id).catch(() => {});
    }, PERSIST_DEBOUNCE_MS);
    this._persistTimers.set(id, timer);
  }

  async flushAll() {
    const ids = new Set([...this.cache.keys(), ...this._persistPending.keys()]);
    await Promise.all([...ids].map((id) => this._flushPersist(id)));
  }

  async _flushPersist(id) {
    this._clearPersistTimer(id);
    const engagement = this.cache.get(id);
    if (!engagement) return;
    try {
      await this.store.upsertEngagement(engagement);
    } catch (err) {
      console.error(`[engagement-manager] Persist failed for ${id}:`, err.message);
      throw err;
    }
  }

  _clearPersistTimer(id) {
    const timer = this._persistTimers.get(id);
    if (timer) clearTimeout(timer);
    this._persistTimers.delete(id);
  }

  async updateEngagement(key, updates) {
    const existing = this.cache.get(String(key));
    if (!existing) return false;
    const updated = { ...existing, ...updates };
    this.cache.set(String(key), updated);
    await this.store.upsertEngagement(updated);
    return true;
  }

  async addLogEntry(key, logEntry) {
    const existing = this.cache.get(String(key));
    if (!existing) return false;
    const logs = Array.isArray(existing.log) ? existing.log : [];
    logs.push(logEntry);
    const updated = { ...existing, log: logs };
    this.cache.set(String(key), updated);
    await this.store.addLogEntry(String(key), logEntry);
    return true;
  }

  async updateStatus(key, status) {
    const updates = { status };
    if (status === "complete" || status === "completed" || status === "error") {
      updates.completed_at = new Date().toISOString();
    }
    return this.updateEngagement(String(key), updates);
  }

  async listAll() {
    return [...this.cache.values()];
  }

  async refreshFromDatabase() {
    await this.store.ready;
    const fresh = await this.store.listEngagements({ limit: 5000 });
    this.cache.clear();
    for (const engagement of fresh) {
      if (engagement?.id) this.cache.set(engagement.id, engagement);
    }
    return fresh.length;
  }

  async getStats() {
    return this.store.getEngagementStats();
  }

  async cleanupOldEngagements(days = 30) {
    const deleted = await this.store.cleanupOldEngagements(days);
    await this.refreshFromDatabase();
    return deleted;
  }

  async close() {
    await this.flushAll();
    await this.store.close();
  }
}

module.exports = EngagementManager;
