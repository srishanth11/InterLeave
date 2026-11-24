package b11_ctxleak

import (
	"context"
	"sync"
)

type Worker struct {
	mu sync.Mutex
}

func (w *Worker) FetchWithTimeout(ctx context.Context, fast bool) (string, bool) {
	resCh := make(chan string)
	go func() {
		w.mu.Lock()
		defer w.mu.Unlock()
		if fast {
			resCh <- "ok"
		}
	}()
	select {
	case v := <-resCh:
		return v, true
	case <-ctx.Done():
		return "", false
	}
}

func CallerQueryService(w *Worker) bool {
	_, ok := w.FetchWithTimeout(context.Background(), true)
	return ok
}
