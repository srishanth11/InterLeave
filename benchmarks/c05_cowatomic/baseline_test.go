package c05_cowatomic

import "testing"

func TestSafeCOW(t *testing.T) {
	r := NewRouter("10.0.0.1", 8080)
	r.Update("10.0.0.2", 9090)
	if !CallerRouteRequest(r) {
		t.Fatal("router failed")
	}
}
