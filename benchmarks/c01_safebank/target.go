package c01_safebank

import "sync"

type SafeAccount struct {
	mu      sync.Mutex
	balance int
}

func NewSafeAccount(initial int) *SafeAccount { return &SafeAccount{balance: initial} }

func (a *SafeAccount) Withdraw(amt int) bool {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.balance >= amt {
		a.balance -= amt
		return true
	}
	return false
}

func CallerSafeATM(a *SafeAccount, amt int) bool {
	return a.Withdraw(amt)
}
