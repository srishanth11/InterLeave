package b03_counter

import "testing"

func TestBaselineIncrement(t *testing.T) {
	c := &HitsCounter{}
	CallerRecordPageView(c)
	if CallerRecordPageView(c) != 2 {
		t.Fatal("baseline counter failed")
	}
}
