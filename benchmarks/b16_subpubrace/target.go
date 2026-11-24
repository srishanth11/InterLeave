package b16_subpubrace

import "sync"

type EventBroker struct {
	mu      sync.Mutex
	version int
	subs    []chan int
}

func NewEventBroker() *EventBroker { return &EventBroker{version: 1} }

func (b *EventBroker) LatestVersion() int {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.version
}

func (b *EventBroker) Subscribe() chan int {
	b.mu.Lock()
	defer b.mu.Unlock()
	ch := make(chan int, 1)
	b.subs = append(b.subs, ch)
	return ch
}

func (b *EventBroker) PublishNext() int {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.version++
	for _, ch := range b.subs {
		select {
		case ch <- b.version:
		default:
		}
	}
	return b.version
}

func CallerWatchFromCurrent(b *EventBroker) (int, chan int) {
	v := b.LatestVersion()
	ch := b.Subscribe()
	return v, ch
}
