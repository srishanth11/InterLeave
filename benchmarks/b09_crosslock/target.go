package b09_crosslock

import "sync"

type Warehouse struct {
	mu    sync.Mutex
	stock int
}

func (w *Warehouse) Add(n int) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.stock += n
}

func (w *Warehouse) Count() int {
	w.mu.Lock()
	defer w.mu.Unlock()
	return w.stock
}

func Rebalance(src, dst *Warehouse, qty int) {
	src.Add(-qty)
	dst.Add(qty)
}

func CallerAuditInventory(w1, w2 *Warehouse) int {
	return w1.Count() + w2.Count()
}
