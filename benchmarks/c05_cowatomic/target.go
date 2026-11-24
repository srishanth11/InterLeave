package c05_cowatomic

import (
	"sync"
	"sync/atomic"
)

type RouteTable struct {
	Host string
	Port int
}

type Router struct {
	mu  sync.Mutex
	cur atomic.Pointer[RouteTable]
}

func NewRouter(host string, port int) *Router {
	r := &Router{}
	r.cur.Store(&RouteTable{Host: host, Port: port})
	return r
}

func (r *Router) Update(host string, port int) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.cur.Store(&RouteTable{Host: host, Port: port})
}

func (r *Router) Get() *RouteTable {
	return r.cur.Load()
}

func CallerRouteRequest(r *Router) bool {
	rt := r.Get()
	return rt != nil && rt.Host != "" && rt.Port > 0
}
