package b18_nestedrw

import "sync"

type Registry struct {
	mu    sync.RWMutex
	items map[string]int
}

func NewRegistry() *Registry {
	return &Registry{items: map[string]int{"core": 1}}
}

func (r *Registry) lookupInternal(k string) int {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return r.items[k]
}

func (r *Registry) ReadWithFallback(primary, fallback string) int {
	r.mu.RLock()
	defer r.mu.RUnlock()
	if v, ok := r.items[primary]; ok {
		return v
	}
	return r.lookupInternal(fallback)
}

func (r *Registry) Update(k string, v int) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.items[k] = v
}

func CallerResolveConfig(r *Registry) int {
	return r.ReadWithFallback("missing", "core")
}
