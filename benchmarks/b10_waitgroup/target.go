package b10_waitgroup

import (
	"sync"
	"sync/atomic"
)

func SpawnAndCollect(n int) int32 {
	var wg sync.WaitGroup
	var completed atomic.Int32
	for i := 0; i < n; i++ {
		go func() {
			wg.Add(1)
			defer wg.Done()
			completed.Add(1)
		}()
	}
	wg.Wait()
	return completed.Load()
}

func CallerRunBatchJobs() int32 {
	return SpawnAndCollect(5)
}
