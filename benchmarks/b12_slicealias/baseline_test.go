package b12_slicealias

import "testing"

func TestBaselineSlice(t *testing.T) {
	d := CallerSplitBuffer()
	if len(d) != 3 {
		t.Fatal("unexpected len")
	}
}
