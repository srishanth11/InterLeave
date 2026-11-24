package c04_actorloop

import "testing"

func TestSafeActor(t *testing.T) {
	a := NewActorLedger(100)
	if !CallerActorPay(a, 70) || CallerActorPay(a, 70) {
		t.Fatal("actor ledger failed")
	}
}
