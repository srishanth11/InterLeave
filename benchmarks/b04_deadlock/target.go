package b04_deadlock

import "sync"

type Wallet struct {
	mu      sync.Mutex
	balance int
}

func NewWallet(bal int) *Wallet { return &Wallet{balance: bal} }

func Transfer(from, to *Wallet, amt int) bool {
	from.mu.Lock()
	defer from.mu.Unlock()
	to.mu.Lock()
	defer to.mu.Unlock()
	if from.balance < amt {
		return false
	}
	from.balance -= amt
	to.balance += amt
	return true
}

func CallerPeerPayment(sender, receiver *Wallet, amt int) bool {
	return Transfer(sender, receiver, amt)
}
