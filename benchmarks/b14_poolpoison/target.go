package b14_poolpoison

import "sync"

type SessionBuf struct {
	mu    sync.Mutex
	owner string
	dirty bool
}

type SessionPool struct {
	mu   sync.Mutex
	free []*SessionBuf
}

func NewSessionPool() *SessionPool {
	return &SessionPool{free: []*SessionBuf{{}}}
}

func (p *SessionPool) Acquire(user string) *SessionBuf {
	p.mu.Lock()
	defer p.mu.Unlock()
	if len(p.free) == 0 {
		return &SessionBuf{owner: user}
	}
	b := p.free[len(p.free)-1]
	p.free = p.free[:len(p.free)-1]
	b.mu.Lock()
	b.owner = user
	b.dirty = false
	b.mu.Unlock()
	return b
}

func (p *SessionPool) Release(b *SessionBuf) {
	p.mu.Lock()
	p.free = append(p.free, b)
	p.mu.Unlock()
}

func CallerHandleSession(p *SessionPool, user string) string {
	buf := p.Acquire(user)
	p.Release(buf)
	buf.mu.Lock()
	buf.dirty = true
	owner := buf.owner
	buf.mu.Unlock()
	return owner
}
