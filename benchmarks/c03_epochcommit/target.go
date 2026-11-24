package c03_epochcommit

import "sync"

type VersionedStore struct {
	mu    sync.Mutex
	val   int
	epoch int
}

func (s *VersionedStore) Read() (int, int) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.val, s.epoch
}

func (s *VersionedStore) CompareAndCommit(expectedEpoch, newVal int) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.epoch != expectedEpoch {
		return false
	}
	s.val = newVal
	s.epoch++
	return true
}

func CallerOptimisticAdd(s *VersionedStore, delta int) bool {
	v, ep := s.Read()
	return s.CompareAndCommit(ep, v+delta)
}
