package b06_rwupgrade

import "testing"

func TestBaselineRefresh(t *testing.T) {
	cache := NewConfigCache()
	if CallerFetchFeatureFlag(cache, "flag") != "enabled-v2" {
		t.Fatal("expected enabled-v2")
	}
	cache.PushUpdate("flag", "enabled-v3")
	if CallerFetchFeatureFlag(cache, "flag") != "enabled-v3" {
		t.Fatal("expected enabled-v3")
	}
}
