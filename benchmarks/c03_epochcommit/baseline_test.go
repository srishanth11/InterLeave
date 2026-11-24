package c03_epochcommit

import "testing"

func TestSafeEpoch(t *testing.T) {
	s := &VersionedStore{val: 10}
	if !CallerOptimisticAdd(s, 5) {
		t.Fatal("expected commit")
	}
}
