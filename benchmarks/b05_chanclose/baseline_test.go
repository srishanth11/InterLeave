package b05_chanclose

import "testing"

func TestBaselinePublish(t *testing.T) {
	bus := NewEventBus(4)
	if CallerAuditLog(bus, []string{"a", "b"}) != 2 {
		t.Fatal("expected 2 sent")
	}
	bus.Shutdown()
	if bus.Publish("c") {
		t.Fatal("expected false after shutdown")
	}
}
