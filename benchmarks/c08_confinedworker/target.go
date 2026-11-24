package c08_confinedworker

type opReq struct {
	key   string
	delta int
	reply chan int
}

type ConfinedStore struct {
	reqs chan opReq
}

func NewConfinedStore() *ConfinedStore {
	s := &ConfinedStore{reqs: make(chan opReq, 16)}
	go s.loop()
	return s
}

func (s *ConfinedStore) loop() {
	state := make(map[string]int)
	for r := range s.reqs {
		state[r.key] += r.delta
		r.reply <- state[r.key]
	}
}

func (s *ConfinedStore) CallerIncrement(key string, delta int) int {
	rep := make(chan int, 1)
	s.reqs <- opReq{key: key, delta: delta, reply: rep}
	return <-rep
}
