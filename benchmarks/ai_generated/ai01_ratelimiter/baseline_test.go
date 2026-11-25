package ai01_ratelimiter

import "testing"

func TestBaselineRateLimiter(t *testing.T) {
	tb := NewTokenBucket(2)
	if !AllowRequest(tb, 2) || tb.Available() != 0 {
		t.Fatal("expected 0 tokens")
	}
}
