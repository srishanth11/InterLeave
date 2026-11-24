package b13_doubletransfer

import "sync"

type Vault struct {
	mu      sync.Mutex
	balance int
}

func NewVault(bal int) *Vault { return &Vault{balance: bal} }

func (v *Vault) Withdraw(amt int) bool {
	v.mu.Lock()
	defer v.mu.Unlock()
	if v.balance < amt {
		return false
	}
	v.balance -= amt
	return true
}

func (v *Vault) Deposit(amt int) {
	v.mu.Lock()
	defer v.mu.Unlock()
	v.balance += amt
}

func (v *Vault) Balance() int {
	v.mu.Lock()
	defer v.mu.Unlock()
	return v.balance
}

func Transfer(src, dst *Vault, amt int) bool {
	if !src.Withdraw(amt) {
		return false
	}
	dst.Deposit(amt)
	return true
}

func CallerAuditConservation(a, b *Vault) int {
	return a.Balance() + b.Balance()
}
