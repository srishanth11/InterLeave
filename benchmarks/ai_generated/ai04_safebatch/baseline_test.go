package ai04_safebatch

import "testing"

func TestSafeMetrics(t *testing.T) {
	m := NewMetrics()
	m.IncRequest()
	r, _ := m.Snapshot()
	if r != 1 {
		t.Fatal("expected 1")
	}
}
