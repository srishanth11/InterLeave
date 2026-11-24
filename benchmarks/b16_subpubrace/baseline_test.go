package b16_subpubrace

import "testing"

func TestBaselineBroker(t *testing.T) {
	b := NewEventBroker()
	v, ch := CallerWatchFromCurrent(b)
	b.PublishNext()
	got := <-ch
	if got != v+1 {
		t.Fatalf("expected %d, got %d", v+1, got)
	}
}
