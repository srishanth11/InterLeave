package b09_crosslock

import "testing"

func TestBaselineRebalance(t *testing.T) {
	w1, w2 := &Warehouse{stock: 50}, &Warehouse{stock: 50}
	Rebalance(w1, w2, 20)
	if CallerAuditInventory(w1, w2) != 100 {
		t.Fatal("stock mismatch")
	}
}
