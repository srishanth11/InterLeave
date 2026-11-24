package b17_timerreset

import (
	"sync"
	"time"
)

type Watchdog struct {
	mu    sync.Mutex
	timer *time.Timer
}

func NewWatchdog(d time.Duration) *Watchdog {
	return &Watchdog{timer: time.NewTimer(d)}
}

func (w *Watchdog) Kick(d time.Duration) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.timer.Stop()
	w.timer.Reset(d)
}

func (w *Watchdog) WaitExpired() bool {
	<-w.timer.C
	return true
}

func CallerExtendDeadline(w *Watchdog) {
	w.Kick(500 * time.Millisecond)
}
