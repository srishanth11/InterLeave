package b02_seat

import "testing"

func TestBaselineReserve(t *testing.T) {
	sm := NewSeatMap()
	if !CallerCheckoutSeat(sm, 12, "Alice") || CallerCheckoutSeat(sm, 12, "Bob") {
		t.Fatal("baseline reserve failed")
	}
}
