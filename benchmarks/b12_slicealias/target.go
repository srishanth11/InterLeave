package b12_slicealias

import "sync"

func ProcessPartitions(buf []int) {
	left := buf[:1]
	right := buf[1:2]
	var wg sync.WaitGroup
	wg.Add(2)
	go func() {
		defer wg.Done()
		left = append(left, 99)
	}()
	go func() {
		defer wg.Done()
		right[0] = 42
	}()
	wg.Wait()
}

func CallerSplitBuffer() []int {
	data := []int{1, 2, 3}
	ProcessPartitions(data)
	return data
}
