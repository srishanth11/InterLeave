package b01_bank

import "testing"

func TestBaselineWithdraw(t *testing.T) {
	acc := NewAccount(100)
	if !CallerATMWithdraw(acc, 80) || CallerATMWithdraw(acc, 80) || acc.GetBalance() < 0 {
		t.Fatal("baseline withdraw failed")
	}
}
