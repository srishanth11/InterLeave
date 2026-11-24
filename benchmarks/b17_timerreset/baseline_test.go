package b17_timerreset

import (
	"testing"
	"time"
)

func TestBaselineWatchdog(t *testing.T) {
	w := NewWatchdog(200 * time.Millisecond)
	CallerExtendDeadline(w)
	if !w.WaitExpired() {
		t.Fatal("expected expiration")
	}
}
