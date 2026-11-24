package c06_semctx

import "testing"

func TestSafeSem(t *testing.T) {
	l := NewLimiter(2)
	if v, ok := CallerRateLimitedWork(l); !ok || v != 7 {
		t.Fatal("limiter failed")
	}
}
