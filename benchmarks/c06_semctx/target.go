package c06_semctx

import "context"

type Limiter struct {
	sem chan struct{}
}

func NewLimiter(max int) *Limiter { return &Limiter{sem: make(chan struct{}, max)} }

func (l *Limiter) Do(ctx context.Context, fn func() int) (int, bool) {
	select {
	case l.sem <- struct{}{}:
		defer func() { <-l.sem }()
		return fn(), true
	case <-ctx.Done():
		return 0, false
	}
}

func CallerRateLimitedWork(l *Limiter) (int, bool) {
	return l.Do(context.Background(), func() int { return 7 })
}
