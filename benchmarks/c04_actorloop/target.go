package c04_actorloop

type req struct {
	amt  int
	resp chan bool
}

type ActorLedger struct {
	ops chan req
}

func NewActorLedger(initial int) *ActorLedger {
	a := &ActorLedger{ops: make(chan req)}
	go func() {
		bal := initial
		for r := range a.ops {
			if bal >= r.amt {
				bal -= r.amt
				r.resp <- true
			} else {
				r.resp <- false
			}
		}
	}()
	return a
}

func (a *ActorLedger) Withdraw(amt int) bool {
	reply := make(chan bool, 1)
	a.ops <- req{amt: amt, resp: reply}
	return <-reply
}

func CallerActorPay(a *ActorLedger, amt int) bool {
	return a.Withdraw(amt)
}
