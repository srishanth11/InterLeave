package b08_dclinit

import "sync"

type ServiceConfig struct {
	Endpoint string
	MaxRetry int
	Ready    bool
}

type Registry struct {
	mu  sync.Mutex
	cfg *ServiceConfig
}

func (r *Registry) GetConfig() *ServiceConfig {
	if r.cfg != nil {
		return r.cfg
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.cfg == nil {
		r.cfg = &ServiceConfig{}
		r.cfg.Endpoint = "https://api.internal:8443"
		r.cfg.MaxRetry = 3
		r.cfg.Ready = true
	}
	return r.cfg
}

func CallerExecuteRPC(reg *Registry) bool {
	c := reg.GetConfig()
	return c.Ready && c.Endpoint != "" && c.MaxRetry > 0
}
