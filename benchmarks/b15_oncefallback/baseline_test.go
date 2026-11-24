package b15_oncefallback

import "testing"

func TestBaselineConn(t *testing.T) {
	m := NewConnManager()
	c, err := CallerConnectWithRetry(m, false)
	if err != nil || c != "connected-db" {
		t.Fatal("expected connected-db")
	}
}
