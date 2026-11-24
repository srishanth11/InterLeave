package b05_chanclose

import (
	"sync"
	"sync/atomic"
)

type EventBus struct {
	ch     chan string
	closed atomic.Bool
	once   sync.Once
}

func NewEventBus(bufSize int) *EventBus { return &EventBus{ch: make(chan string, bufSize)} }

func (b *EventBus) Publish(msg string) bool {
	if b.closed.Load() {
		return false
	}
	b.ch <- msg
	return true
}

func (b *EventBus) Shutdown() {
	b.once.Do(func() {
		b.closed.Store(true)
		close(b.ch)
	})
}

func CallerAuditLog(bus *EventBus, events []string) int {
	sent := 0
	for _, e := range events {
		if bus.Publish(e) {
			sent++
		}
	}
	return sent
}
