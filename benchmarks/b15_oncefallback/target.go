package b15_oncefallback

import (
	"errors"
	"sync"
)

type ConnManager struct {
	once sync.Once
	mu   sync.Mutex
	conn string
	err  error
}

func NewConnManager() *ConnManager { return &ConnManager{} }

func (m *ConnManager) Init(shouldFail bool) (string, error) {
	m.once.Do(func() {
		m.mu.Lock()
		defer m.mu.Unlock()
		if shouldFail {
			m.err = errors.New("dial timeout")
			return
		}
		m.conn = "connected-db"
		m.err = nil
	})
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.conn, m.err
}

func CallerConnectWithRetry(m *ConnManager, fail bool) (string, error) {
	return m.Init(fail)
}
