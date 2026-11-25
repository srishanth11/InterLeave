package ai02_cacheclose

import "testing"

func TestBaselineFlusher(t *testing.T) {
	f := NewAsyncFlusher()
	if !f.Log("hello") {
		t.Fatal("expected log success")
	}
	f.Close()
}
