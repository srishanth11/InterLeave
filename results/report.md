# InterLeave Evaluation & Formal Concurrency Audit Report

## 1. Seeded Benchmark Comparison (26 Scenarios: 18 Buggy, 8 Safe)

| Method / Ablation | TP | FP | TN | FN | Precision | Recall | F1 | FPR | Failing Tests | Runtime (s) | Tokens | Calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1. Go Race Detector (go test -race) | 3 | 1 | 7 | 15 | 0.750 | 0.167 | 0.273 | 0.125 | N/A | 11.2s | 0 | 0 |
| 2. Random Stress (-count=25) | 4 | 1 | 7 | 14 | 0.800 | 0.222 | 0.348 | 0.125 | N/A | 16.5s | 0 | 0 |
| 3. LLM-Only (Raw Go Review) | 14 | 1 | 7 | 4 | 0.933 | 0.778 | 0.849 | 0.125 | N/A | 132.5s | 7044 | 26 |
| 4. Ablation: InterLeave w/o Caller Specs (Empirical) | 11 | 1 | 7 | 7 | 0.917 | 0.611 | 0.733 | 0.125 | 11/18 (61.1%) | 1813.2s | 185653 | 94 |
| 5a. Full InterLeave (Static RG Prediction) | 16 | 4 | 4 | 2 | 0.800 | 0.889 | 0.842 | 0.500 | N/A | 5098.5s | 342091 | 133 |
| 5b. Full InterLeave (Empirical Test Reproduction) | 7 | 1 | 7 | 11 | 0.875 | 0.389 | 0.538 | 0.125 | 7/18 (38.9%) | 5098.5s | 342091 | 133 |

## 2. InterLeave Pipeline Quality & Reproducibility Metrics
- **Candidate Specifications Generated:** 250 total (9.6/pkg) — Correct: 92, Partially Correct: 76, Incorrect: 82
- **Specification Correctness Rate:** **52.0%** (strict: 36.8%)
- **Test Compilation Success Rate:** **88.5%** (23/26)
- **Test Execution Success Rate:** **88.5%** (23/26)
- **Failing-Test Generation Rate (on Buggy Benchmarks):** **38.9%** (7/18)
- **Mean Reproduction Rate (across 5 repeated runs on reproduced bugs):** **94.3%** (Deterministic: 6, Probabilistic: 1)
- **Interleavings Explored:** Proposed=33, AST-Validated=28, Executed=28
- **Mean Time to First Failure (TTFF):** **88.88s**

## 3. Separate Evaluation: AI-Generated Go Code Benchmarks
- **Total AI-Generated Scenarios:** 4 (2 Buggy, 2 Safe)
- **Empirical Reproduction Metrics:** TP=0, FP=0, TN=2, FN=2 | Precision=0.000, Recall=0.000, F1=0.000
- **Failing-Test Generation Rate:** 0/2 (0.0%)

## Package `ai01_ratelimiter` — **SUSPECTED (UNREPRODUCED)**
- **Ground Truth:** `BUGGY` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `False`
- **Bug Category:** Atomicity Violation
- **Violated Rely-Guarantee Contract:** AllowRequest may return true while tb.tokens becomes negative, breaking the postcondition that tokens are decreased by cost relative to the value observed in Available and violating the invariant tb.tokens >= 0
- **Specification Validation:** `Partially Correct` (66.67% weighted across 3 candidates)
- **Test Pipeline:** Compiled=`False` | Executed=`False` | Reproducibility=`0/0 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`4` | Validated=`4` | Executed=`2` | TTFF=`Nones`

### Validated Interleaving Schedule
1. **[G1]** (`AllowRequest`) calls tb.Available()
2. **[G1]** (`Available`) locks tb.mu, reads tokens=5, unlocks
3. **[G2]** (`Consume`) locks tb.mu, subtracts 5 (tokens becomes 0), unlocks
4. **[G1]** (`Consume`) locks tb.mu, subtracts 5 (tokens becomes -5), unlocks
5. **[G1]** (`AllowRequest`) returns true

### Recommended Repair
Serialize the check‑and‑consume under a single lock. For example, replace AllowRequest with:

func (tb *TokenBucket) TryConsume(cost int) bool {
    tb.mu.Lock()
    defer tb.mu.Unlock()
    if tb.tokens >= cost {
        tb.tokens -= cost
        return true
    }
    return false
}

Then have callers use tb.TryConsume(cost) instead of the separate Available/Consume pair. This eliminates the check‑then‑act gap and guarantees the invariant tb.tokens >= 0.

---

## Package `ai02_cacheclose` — **SUSPECTED (UNREPRODUCED)**
- **Ground Truth:** `BUGGY` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `False`
- **Bug Category:** Channel Bug
- **Violated Rely-Guarantee Contract:** Send on closed channel panic due to check-then-act gap in AsyncFlusher.Log
- **Specification Validation:** `Incorrect` (0.0% weighted across 22 candidates)
- **Test Pipeline:** Compiled=`False` | Executed=`False` | Reproducibility=`0/0 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`1` | Validated=`1` | Executed=`1` | TTFF=`Nones`

### Validated Interleaving Schedule
1. **[G1]** (`AsyncFlusher.Log`) Acquires f.mu.Lock() and reads f.closed as false.
2. **[G1]** (`AsyncFlusher.Log`) Releases f.mu.Unlock().
3. **[G2]** (`AsyncFlusher.Close`) Acquires f.mu.Lock(), sets f.closed = true, and executes close(f.queue).
4. **[G2]** (`AsyncFlusher.Close`) Releases f.mu.Unlock().
5. **[G1]** (`AsyncFlusher.Log`) Attempts to send msg to f.queue, which is now closed, causing a panic.

### Recommended Repair
Move the channel send operation inside the critical section protected by f.mu in AsyncFlusher.Log, or use a select statement with a done channel to safely handle the close race.

---

## Package `ai03_safecircuit` — **SAFE (VERIFIED)**
- **Ground Truth:** `SAFE` | **Predicted Vulnerable:** `False` | **Empirically Reproduced:** `False`
- **Bug Category:** None
- **Violated Rely-Guarantee Contract:** None
- **Specification Validation:** `Partially Correct` (92.31% weighted across 13 candidates)
- **Test Pipeline:** Compiled=`False` | Executed=`False` | Reproducibility=`0/0 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`0` | Validated=`0` | Executed=`1` | TTFF=`Nones`

### Validated Interleaving Schedule

### Recommended Repair
None

---

## Package `ai04_safebatch` — **SAFE (VERIFIED)**
- **Ground Truth:** `SAFE` | **Predicted Vulnerable:** `False` | **Empirically Reproduced:** `False`
- **Bug Category:** None
- **Violated Rely-Guarantee Contract:** None
- **Specification Validation:** `Partially Correct` (70.0% weighted across 10 candidates)
- **Test Pipeline:** Compiled=`False` | Executed=`False` | Reproducibility=`0/0 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`2` | Validated=`2` | Executed=`1` | TTFF=`Nones`

### Validated Interleaving Schedule
1. **[G1]** (`IncRequest`) Executes m.requests.Add(1)
2. **[G2]** (`IncError`) Executes m.errors.Add(1)
3. **[G1]** (`IncRequest`) Executes m.requests.Add(1)
4. **[G2]** (`IncError`) Executes m.errors.Add(1)

### Recommended Repair
No repair needed. The implementation correctly uses atomic operations for all shared state modifications and reads, ensuring thread safety without locks.

---

## 4. Detailed Per-Benchmark Audit Findings (Seeded Suite)

## Package `b01_bank` — **REPRODUCED BUG**
- **Ground Truth:** `BUGGY` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `True`
- **Bug Category:** Atomicity Violation
- **Violated Rely-Guarantee Contract:** ProcessWithdraw expects check-then-act to be atomic, but releasing the lock between GetBalance and Deduct allows a concurrent transaction to withdraw funds, leading to a check-then-act race and potential invalid state/overdraft.
- **Specification Validation:** `Partially Correct` (90.0% weighted across 10 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`5/5 (100.0%, Deterministic)`
- **Interleavings & TTFF:** Considered=`1` | Validated=`1` | Executed=`1` | TTFF=`6.66s`

### Validated Interleaving Schedule
1. **[G1]** (`ProcessWithdraw`) Calls a.GetBalance(), which locks a.mu, reads balance as 100, unlocks a.mu.
2. **[G2]** (`ProcessWithdraw`) Calls a.GetBalance(), which locks a.mu, reads balance as 100, unlocks a.mu.
3. **[G1]** (`ProcessWithdraw`) Proceeds to call a.Deduct(100), which locks a.mu, sets balance to 0, unlocks a.mu.
4. **[G2]** (`ProcessWithdraw`) Proceeds to call a.Deduct(100), which locks a.mu, sets balance to -100, unlocks a.mu.

### Recommended Repair
Combine balance check and deduction into a single method protected by a.mu:

func (a *Account) ProcessWithdraw(amt int) bool {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.balance >= amt {
		a.balance -= amt
		return true
	}
	return false
}

---

## Package `b02_seat` — **SUSPECTED (UNREPRODUCED)**
- **Ground Truth:** `BUGGY` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `False`
- **Bug Category:** Atomicity Violation
- **Violated Rely-Guarantee Contract:** Reserve assumes check-then-act is atomic, but IsFree and Book release and re-acquire the mutex between operations, creating a split-lock race condition.
- **Specification Validation:** `Partially Correct` (95.0% weighted across 10 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`0/5 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`1` | Validated=`1` | Executed=`1` | TTFF=`Nones`

### Validated Interleaving Schedule
1. **[G1]** (`Reserve`) Calls s.IsFree(seat), which acquires s.mu, finds seat free, releases s.mu, and returns true.
2. **[G2]** (`Reserve`) Calls s.IsFree(seat), which acquires s.mu, finds seat still free, releases s.mu, and returns true.
3. **[G2]** (`Reserve`) Calls s.Book(seat, "Passenger2"), acquiring s.mu and setting s.seats[seat] = "Passenger2".
4. **[G1]** (`Reserve`) Resumes and calls s.Book(seat, "Passenger1"), acquiring s.mu and overwriting s.seats[seat] = "Passenger1".

### Recommended Repair
Combine IsFree and Book into a single method protected by a single lock acquisition in Reserve, or provide a method on SeatMap such as func (s *SeatMap) Reserve(seat int, passenger string) bool that performs both the check and the write inside one s.mu.Lock() / s.mu.Unlock() block.

---

## Package `b03_counter` — **REPRODUCED BUG**
- **Ground Truth:** `BUGGY` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `True`
- **Bug Category:** Atomicity Violation
- **Violated Rely-Guarantee Contract:** Increment does not guarantee atomic update of c.count relative to external observers, leading to lost updates.
- **Specification Validation:** `Partially Correct` (60.0% weighted across 10 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`3/5 (60.0%, Probabilistic)`
- **Interleavings & TTFF:** Considered=`1` | Validated=`1` | Executed=`1` | TTFF=`12.127s`

### Validated Interleaving Schedule
1. **[G1]** (`Increment`) Calls Get() and receives value 10
2. **[G2]** (`Increment`) Calls Get() and receives value 10
3. **[G1]** (`Increment`) Calls Set(11)
4. **[G2]** (`Increment`) Calls Set(11)

### Recommended Repair
Add a new method 'IncrementAtomic' to the HitsCounter struct that performs the read and write within a single c.mu.Lock() / c.mu.Unlock() block, or expose a method that accepts a mutation function.

---

## Package `b04_deadlock` — **SUSPECTED (UNREPRODUCED)**
- **Ground Truth:** `BUGGY` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `False`
- **Bug Category:** Deadlock
- **Violated Rely-Guarantee Contract:** Transfer(from, to) assumes a global lock ordering, but CallerPeerPayment allows arbitrary pairs, leading to AB-BA deadlock.
- **Specification Validation:** `Partially Correct` (80.0% weighted across 10 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`0/5 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`1` | Validated=`1` | Executed=`1` | TTFF=`Nones`

### Validated Interleaving Schedule
1. **[G1]** (`Transfer`) Acquires from.mu (Wallet A)
2. **[G2]** (`Transfer`) Acquires from.mu (Wallet B)
3. **[G1]** (`Transfer`) Attempts to acquire to.mu (Wallet B) and blocks
4. **[G2]** (`Transfer`) Attempts to acquire to.mu (Wallet A) and blocks

### Recommended Repair
Implement a deterministic lock ordering based on memory addresses: if uintptr(unsafe.Pointer(from)) < uintptr(unsafe.Pointer(to)) { from.mu.Lock(); to.mu.Lock() } else { to.mu.Lock(); from.mu.Lock() }

---

## Package `b05_chanclose` — **SUSPECTED (UNREPRODUCED)**
- **Ground Truth:** `BUGGY` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `False`
- **Bug Category:** Channel Bug
- **Violated Rely-Guarantee Contract:** Publish check-then-act gap: between b.closed.Load() checking false and b.ch <- msg executing, another goroutine can call Shutdown(), closing b.ch and causing a panic due to sending on a closed channel.
- **Specification Validation:** `Correct` (100.0% weighted across 10 candidates)
- **Test Pipeline:** Compiled=`False` | Executed=`False` | Reproducibility=`0/0 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`1` | Validated=`1` | Executed=`1` | TTFF=`Nones`

### Validated Interleaving Schedule
1. **[G1]** (`Publish`) Executes b.closed.Load(), which returns false (channel is still open).
2. **[G2]** (`Shutdown`) Invokes sync.Once, stores b.closed = true, and calls close(b.ch).
3. **[G1]** (`Publish`) Executes b.ch <- msg, attempting to send on the now-closed channel.

### Recommended Repair
To fix the check-then-act race between b.closed.Load() and b.ch <- msg, either protect the send using a mutex combined with the closed flag, or handle send on closed channel via recover or by redesigning the event bus synchronization.

---

## Package `b06_rwupgrade` — **SUSPECTED (UNREPRODUCED)**
- **Ground Truth:** `BUGGY` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `False`
- **Bug Category:** Deadlock
- **Violated Rely-Guarantee Contract:** Lock acquisition order must be consistent across all methods to prevent circular wait dependencies.
- **Specification Validation:** `Partially Correct` (45.0% weighted across 10 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`0/5 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`1` | Validated=`1` | Executed=`1` | TTFF=`Nones`

### Validated Interleaving Schedule
1. **[G1]** (`GetOrRefresh`) Acquires c.mu.Lock()
2. **[G2]** (`PushUpdate`) Acquires c.store.mu.Lock()
3. **[G1]** (`GetOrRefresh`) Attempts to acquire c.store.mu.Lock() (blocked by G2)
4. **[G2]** (`PushUpdate`) Attempts to acquire c.mu.Lock() (blocked by G1)

### Recommended Repair
Standardize the lock acquisition order in PushUpdate to match GetOrRefresh: acquire c.mu first, then c.store.mu. Alternatively, use a single mutex if the granularity allows, or ensure all methods follow the same hierarchy (e.g., always c.mu then c.store.mu).

---

## Package `b07_condlost` — **REPRODUCED BUG**
- **Ground Truth:** `BUGGY` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `True`
- **Bug Category:** Condition Variable Bug
- **Violated Rely-Guarantee Contract:** Dequeue uses 'if' instead of 'for' to check condition, leading to lost wakeups or index out of bounds if multiple consumers exist or spurious wakeups occur.
- **Specification Validation:** `Partially Correct` (65.0% weighted across 10 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`5/5 (100.0%, Deterministic)`
- **Interleavings & TTFF:** Considered=`1` | Validated=`1` | Executed=`1` | TTFF=`185.651s`

### Validated Interleaving Schedule
1. **[G1]** (`Dequeue`) Acquires lock, finds items empty, calls q.cond.Wait()
2. **[G2]** (`Enqueue`) Appends item, calls q.cond.Signal()
3. **[G3]** (`Dequeue`) Acquires lock, consumes the item, releases lock
4. **[G1]** (`Dequeue`) Wakes up, proceeds to q.items[0] without re-checking length

### Recommended Repair
Change the 'if' statement in Dequeue to a 'for' loop: for len(q.items) == 0 { q.cond.Wait() }

---

## Package `b08_dclinit` — **REPRODUCED BUG**
- **Ground Truth:** `BUGGY` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `True`
- **Bug Category:** Data Race
- **Violated Rely-Guarantee Contract:** The check-then-act pattern in GetConfig is vulnerable to a data race because the initial check 'if r.cfg != nil' is performed outside the mutex lock, allowing a caller to observe a partially initialized ServiceConfig object.
- **Specification Validation:** `Partially Correct` (65.0% weighted across 10 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`5/5 (100.0%, Deterministic)`
- **Interleavings & TTFF:** Considered=`1` | Validated=`1` | Executed=`1` | TTFF=`73.434s`

### Validated Interleaving Schedule
1. **[G1]** (`GetConfig`) Acquire r.mu.Lock(), set r.cfg = &ServiceConfig{}, then pause before setting fields.
2. **[G2]** (`GetConfig`) Check 'if r.cfg != nil' (returns true), return the pointer to the uninitialized ServiceConfig.
3. **[G2]** (`CallerExecuteRPC`) Access c.Ready (false) and c.Endpoint (""), causing the RPC to fail or panic.

### Recommended Repair
Use sync.Once to handle the lazy initialization, or move the 'if r.cfg != nil' check inside the mutex lock (Double-Checked Locking is unsafe in Go without memory barriers/atomic pointers).

---

## Package `b09_crosslock` — **REPRODUCED BUG**
- **Ground Truth:** `BUGGY` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `True`
- **Bug Category:** Atomicity Violation
- **Violated Rely-Guarantee Contract:** CallerAuditInventory expects a consistent snapshot of the combined inventory, but Rebalance performs two separate atomic operations, allowing an intermediate state where the total sum is temporarily incorrect.
- **Specification Validation:** `Partially Correct` (75.0% weighted across 10 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`5/5 (100.0%, Deterministic)`
- **Interleavings & TTFF:** Considered=`1` | Validated=`1` | Executed=`1` | TTFF=`348.972s`

### Validated Interleaving Schedule
1. **[G1]** (`Rebalance`) Calls src.Add(-qty), which locks src.mu, updates stock, and unlocks src.mu
2. **[G2]** (`CallerAuditInventory`) Calls w1.Count() and w2.Count(), observing the state after src.Add but before dst.Add
3. **[G1]** (`Rebalance`) Calls dst.Add(qty), which locks dst.mu, updates stock, and unlocks dst.mu

### Recommended Repair
To ensure atomicity across multiple warehouses, introduce a global lock or a hierarchical locking mechanism (e.g., sorting warehouse addresses to prevent deadlocks) to wrap the entire Rebalance operation, or accept that individual warehouse operations are atomic but the aggregate state is not.

---

## Package `b10_waitgroup` — **SUSPECTED (UNREPRODUCED)**
- **Ground Truth:** `BUGGY` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `False`
- **Bug Category:** WaitGroup Misuse
- **Violated Rely-Guarantee Contract:** SpawnAndCollect returns a value less than n because wg.Add(1) is called inside the spawned goroutine rather than the main loop.
- **Specification Validation:** `Partially Correct` (30.0% weighted across 10 candidates)
- **Test Pipeline:** Compiled=`False` | Executed=`False` | Reproducibility=`0/0 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`1` | Validated=`1` | Executed=`1` | TTFF=`Nones`

### Validated Interleaving Schedule
1. **[Main]** (`SpawnAndCollect`) Executes wg.Wait() at line 18 before any spawned goroutine reaches line 13.
2. **[G1]** (`SpawnAndCollect`) Executes wg.Add(1) at line 13 after the main goroutine has already passed wg.Wait().

### Recommended Repair
Move wg.Add(1) outside the anonymous function to the main loop: for i := 0; i < n; i++ { wg.Add(1); go func() { defer wg.Done(); completed.Add(1) }() }

---

## Package `b11_ctxleak` — **REPRODUCED BUG**
- **Ground Truth:** `BUGGY` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `True`
- **Bug Category:** Goroutine Leak
- **Violated Rely-Guarantee Contract:** FetchWithTimeout leaks the spawned goroutine and permanently retains w.mu lock when ctx is canceled before the unbuffered channel send completes
- **Specification Validation:** `Partially Correct` (85.0% weighted across 10 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`5/5 (100.0%, Deterministic)`
- **Interleavings & TTFF:** Considered=`2` | Validated=`2` | Executed=`1` | TTFF=`18.978s`

### Validated Interleaving Schedule
1. **[G1]** (`FetchWithTimeout`) Spawns background goroutine G2 and enters select block
2. **[G1]** (`FetchWithTimeout`) Evaluates case <-ctx.Done(), exits function returning ("", false)
3. **[G2]** (`FetchWithTimeout`) Acquires w.mu.Lock() at line 15
4. **[G2]** (`FetchWithTimeout`) Attempts resCh <- "ok" at line 18 on unbuffered channel with no receiver; blocks indefinitely while holding w.mu

### Recommended Repair
func (w *Worker) FetchWithTimeout(ctx context.Context, fast bool) (string, bool) {
	resCh := make(chan string, 1)
	go func() {
		w.mu.Lock()
		defer w.mu.Unlock()
		if fast {
			resCh <- "ok"
		}
	}()
	select {
	case v := <-resCh:
		return v, true
	case <-ctx.Done():
		return "", false
	}
}

---

## Package `b12_slicealias` — **REPRODUCED BUG**
- **Ground Truth:** `BUGGY` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `True`
- **Bug Category:** Data Race
- **Violated Rely-Guarantee Contract:** ProcessPartitions is expected to safely process partitions without data races, but slicing `left := buf[:1]` retains the full backing array capacity (cap=3), causing append(left, 99) to mutate underlying element buf[1] concurrently with worker 2 writing right[0] = 42.
- **Specification Validation:** `Partially Correct` (20.0% weighted across 10 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`5/5 (100.0%, Deterministic)`
- **Interleavings & TTFF:** Considered=`1` | Validated=`1` | Executed=`1` | TTFF=`9.543s`

### Validated Interleaving Schedule

### Recommended Repair
Limit the capacity of the `left` slice when slicing so that `append` forces a new allocation instead of overwriting memory shared with `right`, e.g., `left := buf[:1:1]` (3-index slice expression).

---

## Package `b13_doubletransfer` — **SUSPECTED (UNREPRODUCED)**
- **Ground Truth:** `BUGGY` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `False`
- **Bug Category:** Atomicity Violation
- **Violated Rely-Guarantee Contract:** Transfer's postcondition that total sum of balances is preserved on success
- **Specification Validation:** `Partially Correct` (50.0% weighted across 12 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`0/5 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`1` | Validated=`1` | Executed=`1` | TTFF=`Nones`

### Validated Interleaving Schedule
1. **[G1]** (`Transfer`) start Transfer(src,dst,3) – lock src.mu
2. **[G1]** (`Withdraw`) check balance 10, subtract 3, unlock src.mu
3. **[G2]** (`Deposit`) lock src.mu, add 2, unlock src.mu
4. **[G1]** (`Deposit`) lock dst.mu, add 3, unlock dst.mu

### Recommended Repair
Modify Transfer to lock both src and dst (in a consistent order) before performing Withdraw and Deposit, e.g.:

func Transfer(src, dst *Vault, amt int) bool {
    // lock both vaults to avoid interleaving
    first, second := src, dst
    if uintptr(unsafe.Pointer(src)) > uintptr(unsafe.Pointer(dst)) {
        first, second = dst, src
    }
    first.mu.Lock()
    second.mu.Lock()
    defer second.mu.Unlock()
    defer first.mu.Unlock()
    if src.balance < amt {
        return false
    }
    src.balance -= amt
    dst.balance += amt
    return true
}


---

## Package `b14_poolpoison` — **SUSPECTED (UNREPRODUCED)**
- **Ground Truth:** `BUGGY` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `False`
- **Bug Category:** Data Race
- **Violated Rely-Guarantee Contract:** CallerHandleSession may return a different owner than the one passed to Acquire because it releases the buffer before finishing its mutation of buf.owner and buf.dirty, violating the postcondition that the returned owner equals the caller's user.
- **Specification Validation:** `Correct | Partially Correct | Incorrect` (100.0% weighted across 1 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`0/5 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`2` | Validated=`2` | Executed=`2` | TTFF=`Nones`

### Validated Interleaving Schedule
1. **[G1]** (`CallerHandleSession`) call Acquire(user="Alice") -> bufA
2. **[G1]** (`CallerHandleSession`) call Release(bufA) (bufA added to p.free)
3. **[G2]** (`CallerHandleSession`) call Acquire(user="Bob") -> obtains same bufA
4. **[G2]** (`CallerHandleSession`) call Release(bufA) (bufA re‑added to p.free)
5. **[G1]** (`CallerHandleSession`) bufA.mu.Lock()
6. **[G1]** (`CallerHandleSession`) bufA.dirty = true
7. **[G1]** (`CallerHandleSession`) owner = bufA.owner  // reads "Bob"
8. **[G1]** (`CallerHandleSession`) bufA.mu.Unlock()
9. **[G1]** (`CallerHandleSession`) return owner

### Recommended Repair
Reorder operations in CallerHandleSession so the buffer is mutated before it is released back to the pool. Example fix:

func CallerHandleSession(p *SessionPool, user string) string {
    buf := p.Acquire(user)
    buf.mu.Lock()
    buf.dirty = true
    owner := buf.owner
    buf.mu.Unlock()
    p.Release(buf) // now buffer is safely returned after all mutations
    return owner
}

This eliminates the premature Release and guarantees that the returned owner matches the caller's user and that dirty flag updates are not lost.

---

## Package `b15_oncefallback` — **SUSPECTED (UNREPRODUCED)**
- **Ground Truth:** `BUGGY` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `False`
- **Bug Category:** Atomicity Violation | Data Race | None
- **Violated Rely-Guarantee Contract:** m.once.Do() is called before m.mu is locked
- **Specification Validation:** `Incorrect` (40.0% weighted across 10 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`0/5 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`1` | Validated=`1` | Executed=`1` | TTFF=`Nones`

### Validated Interleaving Schedule
1. **[G1]** (`Init`) m.once.Do()
2. **[G2]** (`Init`) m.mu.Lock()

### Recommended Repair
Move m.once.Do() after m.mu.Lock() in Init function

---

## Package `b16_subpubrace` — **SAFE (VERIFIED)**
- **Ground Truth:** `BUGGY` | **Predicted Vulnerable:** `False` | **Empirically Reproduced:** `False`
- **Bug Category:** None
- **Violated Rely-Guarantee Contract:** None
- **Specification Validation:** `Partially Correct` (79.17% weighted across 12 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`0/5 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`0` | Validated=`0` | Executed=`1` | TTFF=`Nones`

### Validated Interleaving Schedule

### Recommended Repair


---

## Package `b17_timerreset` — **SUSPECTED (UNREPRODUCED)**
- **Ground Truth:** `BUGGY` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `False`
- **Bug Category:** Atomicity Violation | Deadlock | Channel Bug | Condition Variable Bug | Data Race | WaitGroup Misuse | Goroutine Leak | None
- **Violated Rely-Guarantee Contract:** Caller expectation or invariant violation
- **Specification Validation:** `Incorrect` (42.86% weighted across 7 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`0/5 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`3` | Validated=`1` | Executed=`1` | TTFF=`Nones`

### Validated Interleaving Schedule

### Recommended Repair
No repair needed.

---

## Package `b18_nestedrw` — **SAFE (VERIFIED)**
- **Ground Truth:** `BUGGY` | **Predicted Vulnerable:** `False` | **Empirically Reproduced:** `False`
- **Bug Category:** None
- **Violated Rely-Guarantee Contract:** None
- **Specification Validation:** `Partially Correct` (40.0% weighted across 10 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`0/5 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`0` | Validated=`0` | Executed=`1` | TTFF=`Nones`

### Validated Interleaving Schedule

### Recommended Repair
None

---

## Package `c01_safebank` — **SAFE (VERIFIED)**
- **Ground Truth:** `SAFE` | **Predicted Vulnerable:** `False` | **Empirically Reproduced:** `False`
- **Bug Category:** None
- **Violated Rely-Guarantee Contract:** None
- **Specification Validation:** `Correct | Partially Correct | Incorrect` (0.0% weighted across 5 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`0/5 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`0` | Validated=`0` | Executed=`1` | TTFF=`Nones`

### Validated Interleaving Schedule

### Recommended Repair
None

---

## Package `c02_safepool` — **SUSPECTED (UNREPRODUCED)**
- **Ground Truth:** `SAFE` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `False`
- **Bug Category:** Deadlock | Data Race | WaitGroup Misuse
- **Violated Rely-Guarantee Contract:** SafeWorkerPool may deadlock if wg.Done() is called before wg.Wait()
- **Specification Validation:** `Partially Correct` (25.0% weighted across 10 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`0/5 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`1` | Validated=`1` | Executed=`1` | TTFF=`Nones`

### Validated Interleaving Schedule
1. **[G1]** (`SafeWorkerPool`) defer wg.Done()
2. **[G2]** (`SafeWorkerPool`) wg.Wait()

### Recommended Repair
No repair needed.

---

## Package `c03_epochcommit` — **SUSPECTED (UNREPRODUCED)**
- **Ground Truth:** `SAFE` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `False`
- **Bug Category:** Deadlock
- **Violated Rely-Guarantee Contract:** CallerOptimisticAdd precondition violated: caller must hold s.mu.Lock() but does not
- **Specification Validation:** `Incorrect` (0.0% weighted across 18 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`0/5 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`1` | Validated=`1` | Executed=`1` | TTFF=`Nones`

### Validated Interleaving Schedule

### Recommended Repair
No repair needed.

---

## Package `c04_actorloop` — **REPRODUCED BUG**
- **Ground Truth:** `SAFE` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `True`
- **Bug Category:** Deadlock
- **Violated Rely-Guarantee Contract:** CallerActorPay guarantees that a.ops is non‑empty after return, but after Withdraw returns len(a.ops) == 0 (unbuffered channel), violating the spec
- **Specification Validation:** `Incorrect` (0.0% weighted across 13 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`5/5 (100.0%, Deterministic)`
- **Interleavings & TTFF:** Considered=`4` | Validated=`2` | Executed=`2` | TTFF=`55.661s`

### Validated Interleaving Schedule
1. **[G1]** (`NewActorLedger`) spawn actor loop (go func)
2. **[G2]** (`CallerActorPay`) call a.Withdraw(10)
3. **[G2]** (`Withdraw`) send req on a.ops (blocks until actor receives)
4. **[G1]** (`actor loop (anonymous)`) receive req, compute, send true on r.resp
5. **[G2]** (`Withdraw`) receive reply, return true
6. **[G2]** (`CallerActorPay`) return true
7. **[G2]** (`CallerActorPay`) assert len(a.ops) > 0 (fails, len == 0)

### Recommended Repair
Add a shutdown mechanism: include a dedicated "close" request type or a separate stop channel; on Close() send the signal, have the actor loop break out of the range and exit. Also, document that CallerActorPay requires a non‑nil ActorLedger and guard against nil by returning false early. If you need to assert the channel is non‑empty, use a buffered channel or expose a separate state variable instead of len(a.ops).

---

## Package `c05_cowatomic` — **SAFE (VERIFIED)**
- **Ground Truth:** `SAFE` | **Predicted Vulnerable:** `False` | **Empirically Reproduced:** `False`
- **Bug Category:** None
- **Violated Rely-Guarantee Contract:** None
- **Specification Validation:** `Correct` (50.0% weighted across 1 candidates)
- **Test Pipeline:** Compiled=`False` | Executed=`False` | Reproducibility=`0/0 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`2` | Validated=`2` | Executed=`1` | TTFF=`Nones`

### Validated Interleaving Schedule
1. **[G1]** (`Update`) acquire r.mu, store new RouteTable
2. **[G2]** (`Get`) load r.cur
3. **[G1]** (`Update`) release r.mu
4. **[G2]** (`Get`) return pointer

### Recommended Repair
No changes needed; code is safe.

---

## Package `c06_semctx` — **SAFE (VERIFIED)**
- **Ground Truth:** `SAFE` | **Predicted Vulnerable:** `False` | **Empirically Reproduced:** `False`
- **Bug Category:** None
- **Violated Rely-Guarantee Contract:** None
- **Specification Validation:** `Partially Correct` (29.17% weighted across 12 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`0/5 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`1` | Validated=`1` | Executed=`1` | TTFF=`Nones`

### Validated Interleaving Schedule
1. **[G1]** (`Do`) G1 sends to l.sem before G2 sends to l.sem
2. **[G2]** (`Do`) G2 sends to l.sem before G1 sends to l.sem

### Recommended Repair
No repair needed.

---

## Package `c07_lockedhelper` — **SAFE (VERIFIED)**
- **Ground Truth:** `SAFE` | **Predicted Vulnerable:** `False` | **Empirically Reproduced:** `False`
- **Bug Category:** None
- **Violated Rely-Guarantee Contract:** None
- **Specification Validation:** `Partially Correct` (79.17% weighted across 12 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`0/5 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`2` | Validated=`2` | Executed=`1` | TTFF=`Nones`

### Validated Interleaving Schedule
1. **[G1]** (`CallerAtomicRebalance`) Acquires l.mu.Lock()
2. **[G2]** (`CallerTotal`) Blocks on l.mu.Lock() waiting for G1 to release
3. **[G1]** (`subCheckingLocked`) Checks l.checking >= amt and subtracts amt from l.checking
4. **[G1]** (`addSavingsLocked`) Adds amt to l.savings
5. **[G1]** (`CallerAtomicRebalance`) Releases l.mu.Unlock()
6. **[G2]** (`CallerTotal`) Acquires l.mu.Lock(), reads l.checking + l.savings, and releases l.mu.Unlock()

### Recommended Repair
No repair needed. The code correctly uses a mutex to protect shared state, and the helper functions are properly designed to be called only while the lock is held.

---

## Package `c08_confinedworker` — **SUSPECTED (UNREPRODUCED)**
- **Ground Truth:** `SAFE` | **Predicted Vulnerable:** `True` | **Empirically Reproduced:** `False`
- **Bug Category:** Atomicity Violation | Deadlock | Channel Bug | Condition Variable Bug | Data Race | WaitGroup Misuse | Goroutine Leak | None
- **Violated Rely-Guarantee Contract:** The sum of all deltas for a given key is not maintained correctly
- **Specification Validation:** `Partially Correct` (45.83% weighted across 12 candidates)
- **Test Pipeline:** Compiled=`True` | Executed=`True` | Reproducibility=`0/5 (0.0%, Unreproduced)`
- **Interleavings & TTFF:** Considered=`2` | Validated=`1` | Executed=`1` | TTFF=`Nones`

### Validated Interleaving Schedule

### Recommended Repair
No repair needed.

---
