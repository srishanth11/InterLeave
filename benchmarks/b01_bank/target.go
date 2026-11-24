package b01_bank

import "sync"

type Account struct {
	mu      sync.Mutex
	balance int
}

func NewAccount(initial int) *Account { return &Account{balance: initial} }

func (a *Account) GetBalance() int {
	a.mu.Lock()
	defer a.mu.Unlock()
	return a.balance
}

func (a *Account) Deduct(amt int) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.balance -= amt
}

func ProcessWithdraw(a *Account, amt int) bool {
	if a.GetBalance() >= amt {
		a.Deduct(amt)
		return true
	}
	return false
}

func CallerATMWithdraw(a *Account, amt int) bool {
	return ProcessWithdraw(a, amt)
}
