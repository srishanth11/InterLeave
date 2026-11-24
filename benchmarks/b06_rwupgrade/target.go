package b06_rwupgrade

import "sync"

type BackendStore struct {
	mu   sync.Mutex
	data map[string]string
}

type ConfigCache struct {
	mu      sync.Mutex
	entries map[string]string
	store   *BackendStore
}

func NewConfigCache() *ConfigCache {
	return &ConfigCache{
		entries: make(map[string]string),
		store:   &BackendStore{data: map[string]string{"flag": "enabled-v2"}},
	}
}

// GetOrRefresh acquires Cache.mu first, then Store.mu on a cache miss.
func (c *ConfigCache) GetOrRefresh(key string) string {
	c.mu.Lock()
	defer c.mu.Unlock()

	if val, ok := c.entries[key]; ok {
		return val
	}
	c.store.mu.Lock()
	defer c.store.mu.Unlock()

	val := c.store.data[key]
	c.entries[key] = val
	return val
}

// PushUpdate acquires Store.mu first, then Cache.mu to invalidate stale entries.
// BUG: Lock-order inversion (Store.mu -> Cache.mu vs Cache.mu -> Store.mu).
func (c *ConfigCache) PushUpdate(key, val string) {
	c.store.mu.Lock()
	defer c.store.mu.Unlock()

	c.mu.Lock()
	defer c.mu.Unlock()

	c.store.data[key] = val
	delete(c.entries, key)
}

func CallerFetchFeatureFlag(cache *ConfigCache, key string) string {
	return cache.GetOrRefresh(key)
}
