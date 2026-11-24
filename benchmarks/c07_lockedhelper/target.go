package c07_lockedhelper

import "sync"

type Ledger struct {
	mu       sync.Mutex
	checking int
	savings  int
}

func NewLedger(c, s int) *Ledger { return &Ledger{checking: c, savings: s} }

func (l *Ledger) subCheckingLocked(amt int) bool {
	if l.checking < amt {
		return false
	}
	l.checking -= amt
	return true
}

func (l *Ledger) addSavingsLocked(amt int) {
	l.savings += amt
}

func CallerAtomicRebalance(l *Ledger, amt int) bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	if !l.subCheckingLocked(amt) {
		return false
	}
	l.addSavingsLocked(amt)
	return true
}

func CallerTotal(l *Ledger) int {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.checking + l.savings
}
