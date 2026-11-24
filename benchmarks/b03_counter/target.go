package b03_counter

import "sync"

type HitsCounter struct {
	mu    sync.Mutex
	count int
}

func (c *HitsCounter) Get() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.count
}

func (c *HitsCounter) Set(val int) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.count = val
}

func Increment(c *HitsCounter) {
	curr := c.Get()
	c.Set(curr + 1)
}

func CallerRecordPageView(c *HitsCounter) int {
	Increment(c)
	return c.Get()
}
