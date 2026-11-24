package b13_doubletransfer

import "testing"

func TestBaselineTransfer(t *testing.T) {
	a, b := NewVault(200), NewVault(200)
	if !Transfer(a, b, 50) {
		t.Fatal("transfer failed")
	}
	if CallerAuditConservation(a, b) != 400 {
		t.Fatal("conservation violated")
	}
}
