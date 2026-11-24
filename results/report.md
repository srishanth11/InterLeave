# InterleaveGuard Evaluation & Audit Report

## Comparative Benchmark Metrics (18 Go Concurrency Scenarios: 12 Buggy, 6 Safe)

| Method / Ablation | TP | FP | TN | FN | Precision | Recall | F1 Score | Runtime (s) | Total Tokens |
|---|---|---|---|---|---|---|---|---|---|
| 1. go test -race (Baseline) | 1 | 0 | 8 | 17 | 1.00 | 0.06 | 0.11 | 2.2s | 0 |
| 2. Random Stress (-count=25) | 3 | 0 | 8 | 15 | 1.00 | 0.17 | 0.29 | 42.6s | 0 |
| 3. LLM Impl-Only (Ablation) | 18 | 1 | 7 | 0 | 0.95 | 1.00 | 0.97 | 0.0s | 0 |
| 4. InterleaveGuard (Full RG + TestGen) | 18 | 0 | 8 | 0 | 1.00 | 1.00 | 1.00 | 546.3s | 23564 |

## Detailed Per-Benchmark Audit Findings

## Package `b01_bank` — **VULNERABLE**
- **Ground Truth:** `BUGGY` | **Detected:** `True`
- **Bug Category:** Atomicity Violation
- **Violated Rely-Guarantee Contract:** ProcessWithdraw expects check-then-act (GetBalance followed by Deduct) to be atomic, but individual method calls release and re-acquire the lock, creating a split-lock race condition.
- **Empirical Test Witnessed Bug:** `False` (Compiled: `True`)

### Adversarial Interleaving Schedule
1. **[G1]** ProcessWithdraw calls a.GetBalance(); acquires mu, reads balance = 100, releases mu.
2. **[G2]** ProcessWithdraw calls a.Deduct(100); acquires mu, deducts 100, balance becomes 0, releases mu.
3. **[G1]** Resumes ProcessWithdraw with stored balance 100 >= amt (100). Calls a.Deduct(100), balance becomes -100 (overdraws).

### Recommended Repair
Add a Withdraw method on Account that holds the mutex continuously across the check and deduction:
func (a *Account) Withdraw(amt int) bool {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.balance >= amt {
		a.balance -= amt
		return true
	}
	return false
}

---

## Package `b02_seat` — **VULNERABLE**
- **Ground Truth:** `BUGGY` | **Detected:** `True`
- **Bug Category:** Atomicity Violation
- **Violated Rely-Guarantee Contract:** Reserve expects IsFree and Book to act as a single atomic compound operation, but the mutex is released between IsFree and Book, leading to a check-then-act race gap.
- **Empirical Test Witnessed Bug:** `True` (Compiled: `True`)

### Adversarial Interleaving Schedule
1. **[G1]** CallerCheckoutSeat calls Reserve(s, 1, "Alice"), which calls s.IsFree(1). G1 acquires s.mu, finds seat 1 free, and releases s.mu.
2. **[G2]** Concurrent goroutine G2 calls Reserve(s, 1, "Bob"). G2 acquires s.mu, finds seat 1 free, books it for "Bob", and releases s.mu.
3. **[G1]** G1 resumes Reserve, proceeds to s.Book(1, "Alice"), acquiring s.mu and overwriting Bob's reservation with Alice's without re-verifying if the seat is still free.

### Recommended Repair
Introduce an atomic Reserve method that holds the mutex across both the check and the write:

func (s *SeatMap) Reserve(seat int, passenger string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, taken := s.seats[seat]; taken {
		return false
	}
	s.seats[seat] = passenger
	return true
}

---

## Package `b03_counter` — **VULNERABLE**
- **Ground Truth:** `BUGGY` | **Detected:** `True`
- **Bug Category:** Atomicity Violation
- **Violated Rely-Guarantee Contract:** Increment expects to atomically increment c.count, but releases and re-acquires c.mu between Get() and Set(), creating a check-then-act race condition.
- **Empirical Test Witnessed Bug:** `True` (Compiled: `True`)

### Adversarial Interleaving Schedule
1. **[G1]** Calls Increment(c), which calls c.Get(). G1 locks c.mu, reads c.count (e.g., 0), unlocks c.mu.
2. **[G2]** Calls Increment(c). G2 locks c.mu, reads c.count (0), sets c.count to 1, unlocks c.mu.
3. **[G1]** Resumes Increment(c), calls c.Set(curr + 1) where curr was 0. G1 sets c.count to 1, overwriting G2's update.

### Recommended Repair
Combine Get and Set into a single method protected by one critical section, or add a method: func (c *HitsCounter) Increment() { c.mu.Lock(); defer c.mu.Unlock(); c.count++ }

---

## Package `b04_deadlock` — **VULNERABLE**
- **Ground Truth:** `BUGGY` | **Detected:** `True`
- **Bug Category:** Deadlock
- **Violated Rely-Guarantee Contract:** Transfer relies on other goroutines not locking in a conflicting order, but the implementation lacks a global lock ordering strategy (e.g., sorting by memory address).
- **Empirical Test Witnessed Bug:** `False` (Compiled: `True`)

### Adversarial Interleaving Schedule
1. **[G1]** Transfer(walletA, walletB, 10) calls walletA.mu.Lock()
2. **[G2]** Transfer(walletB, walletA, 10) calls walletB.mu.Lock()
3. **[G1]** Attempts to call walletB.mu.Lock() and blocks
4. **[G2]** Attempts to call walletA.mu.Lock() and blocks (Deadlock)

### Recommended Repair
Implement lock ordering based on memory addresses: if uintptr(unsafe.Pointer(from)) < uintptr(unsafe.Pointer(to)) { from.mu.Lock(); to.mu.Lock() } else { to.mu.Lock(); from.mu.Lock() }

---

## Package `b05_chanclose` — **VULNERABLE**
- **Ground Truth:** `BUGGY` | **Detected:** `True`
- **Bug Category:** Atomicity Violation
- **Violated Rely-Guarantee Contract:** Publish relies on b.ch not being closed while executing, but the check-then-act gap between b.closed.Load() and b.ch <- msg allows a concurrent Shutdown to close the channel, causing a panic.
- **Empirical Test Witnessed Bug:** `False` (Compiled: `True`)

### Adversarial Interleaving Schedule
1. **[G1 (Publish)]** b.closed.Load() returns false
2. **[G2 (Shutdown)]** b.once.Do executes, sets b.closed=true, and closes b.ch
3. **[G1 (Publish)]** b.ch <- msg executes on a closed channel, causing a panic

### Recommended Repair
The channel cannot be safely protected by an atomic bool alone because the channel operation is not atomic with the check. Use a sync.RWMutex to protect the channel send and the closed state, or use a select statement with a 'done' channel to signal shutdown instead of closing the data channel.

---

## Package `b06_rwupgrade` — **VULNERABLE**
- **Ground Truth:** `BUGGY` | **Detected:** `True`
- **Bug Category:** Deadlock
- **Violated Rely-Guarantee Contract:** Inconsistent lock acquisition order between GetOrRefresh and PushUpdate
- **Empirical Test Witnessed Bug:** `False` (Compiled: `True`)

### Adversarial Interleaving Schedule
1. **[G1]** Caller calls GetOrRefresh(key), acquires c.mu (line 25)
2. **[G2]** Caller calls PushUpdate(key, val), acquires c.store.mu (line 42)
3. **[G1]** G1 attempts to acquire c.store.mu (line 31) and blocks waiting for G2
4. **[G2]** G2 attempts to acquire c.mu (line 45) and blocks waiting for G1, resulting in a classic lock-ordering deadlock

### Recommended Repair
Ensure a consistent lock acquisition order across all methods. For example, always acquire c.mu before c.store.mu in both GetOrRefresh and PushUpdate, or redesign the locking hierarchy so that nested locks are avoided.

---

## Package `b07_condlost` — **VULNERABLE**
- **Ground Truth:** `BUGGY` | **Detected:** `True`
- **Bug Category:** Condition Variable Bug
- **Violated Rely-Guarantee Contract:** Dequeue uses 'if len(q.items) == 0' instead of a 'for' loop for condition predicate checking, leading to lost wakeups and spurious wakeups.
- **Empirical Test Witnessed Bug:** `False` (Compiled: `True`)

### Adversarial Interleaving Schedule
1. **[G1 (Dequeue)]** Acquires q.mu, checks len(q.items) == 0 (true), and calls q.cond.Wait() which releases the lock and blocks.
2. **[G2 (Enqueue)]** Acquires q.mu, appends an item, releases q.mu, and calls q.cond.Signal(). G1 is woken up.
3. **[G3 (Dequeue)]** Intervenes before G1 reacquires the lock or finishes, calls Dequeue, acquires q.mu, consumes the item from q.items, and releases q.mu.
4. **[G1 (Dequeue)]** Reacquires q.mu after being signaled, but proceeds directly to access q.items[0] without re-checking the condition. Since G3 already took the item, q.items is empty again, causing a panic (index out of range) or returning an incorrect value.

### Recommended Repair
Replace the 'if' statement in Dequeue with a 'for' loop to re-check the predicate upon waking up: 

func (q *TaskQueue) Dequeue() int {
	q.mu.Lock()
	defer q.mu.Unlock()
	for len(q.items) == 0 {
		q.cond.Wait()
	}
	item := q.items[0]
	q.items = q.items[1:]
	return item
}

---

## Package `b08_dclinit` — **VULNERABLE**
- **Ground Truth:** `BUGGY` | **Detected:** `True`
- **Bug Category:** Data Race
- **Violated Rely-Guarantee Contract:** Double-checked locking without proper memory barriers or full mutex protection (Check-then-act / data race on r.cfg)
- **Empirical Test Witnessed Bug:** `True` (Compiled: `True`)

### Adversarial Interleaving Schedule
1. **[G1]** GetConfig checks r.cfg != nil without holding r.mu (line 17)
2. **[G2]** GetConfig acquires r.mu.Lock() and initializes r.cfg (lines 20-27)
3. **[G1]** G1 reads r.cfg fields or returns r.cfg while G2 was writing to it, causing an uncoordinated read-write data race on ServiceConfig fields.

### Recommended Repair
Remove the unsafe check outside the lock and use standard mutex protection or sync.Once for initialization: 
func (r *Registry) GetConfig() *ServiceConfig {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.cfg == nil {
		r.cfg = &ServiceConfig{
			Endpoint: "https://api.internal:8443",
			MaxRetry: 3,
			Ready:    true,
		}
	}
	return r.cfg
}

---

## Package `b09_crosslock` — **VULNERABLE**
- **Ground Truth:** `BUGGY` | **Detected:** `True`
- **Bug Category:** Atomicity Violation
- **Violated Rely-Guarantee Contract:** Rebalance updates src and dst in two separate lock/unlock critical sections, leaving an intermediate window where neither the sum invariant holds globally nor is the multi-warehouse transfer atomic.
- **Empirical Test Witnessed Bug:** `False` (Compiled: `True`)

### Adversarial Interleaving Schedule
1. **[G1]** Rebalance(src, dst, 10) calls src.Add(-10), acquiring src.mu, decrementing src.stock, and releasing src.mu
2. **[G2]** CallerAuditInventory(src, dst) executes src.Count() and dst.Count(), observing the intermediate state where src.stock is decremented before dst.stock is incremented, violating the guarantee that the sum remains invariant across the operation from an outside observer's perspective.
3. **[G1]** Rebalance calls dst.Add(10), acquiring dst.mu, incrementing dst.stock, and releasing dst.mu

### Recommended Repair
To make multi-warehouse transfers atomic, acquire locks in a consistent global order (e.g., ordered by memory address or ID) inside a higher-level transaction or transfer function, or protect multi-warehouse operations with a higher-level synchronization mechanism.

---

## Package `b10_waitgroup` — **VULNERABLE**
- **Ground Truth:** `BUGGY` | **Detected:** `True`
- **Bug Category:** WaitGroup Misuse
- **Violated Rely-Guarantee Contract:** SpawnAndCollect spawns goroutines where wg.Add(1) is called *inside* the spawned goroutine instead of *before* spawning it, leading to a race condition where wg.Wait() may return prematurely before all goroutines have actually started or completed.
- **Empirical Test Witnessed Bug:** `True` (Compiled: `True`)

### Adversarial Interleaving Schedule
1. **[Main]** SpawnAndCollect calls go func() i=0
2. **[Main]** SpawnAndCollect calls wg.Wait() before the spawned goroutine executes wg.Add(1)
3. **[Main]** wg.Wait() returns immediately because WaitGroup counter is still 0
4. **[Spawned]** Goroutine finally runs, calls wg.Add(1), but wg.Wait() has already unblocked

### Recommended Repair
Move wg.Add(1) outside and before the go func() call:
for i := 0; i < n; i++ {
	wg.Add(1)
	go func() {
		defer wg.Done()
		completed.Add(1)
	}()
}

---

## Package `b11_ctxleak` — **VULNERABLE**
- **Ground Truth:** `BUGGY` | **Detected:** `True`
- **Bug Category:** Goroutine Leak
- **Violated Rely-Guarantee Contract:** FetchWithTimeout avoids blocking spawned goroutine indefinitely when context times out or is cancelled
- **Empirical Test Witnessed Bug:** `False` (Compiled: `True`)

### Adversarial Interleaving Schedule
1. **[G1 (CallerQueryService)]** Calls FetchWithTimeout with a context that immediately times out or gets cancelled (or simulate slow path where ctx.Done() fires first).
2. **[G2 (Spawned background goroutine)]** Executes w.mu.Lock() and blocks waiting for the mutex (if held externally), or runs and attempts unbuffered resCh <- "ok" send.
3. **[G1 (FetchWithTimeout)]** select statement selects <-ctx.Done() because resCh is unbuffered and nobody is receiving from it yet, returning immediately and abandoning the spawned goroutine.
4. **[G2 (Spawned background goroutine)]** Attempts to send on resCh <- "ok", but since G1 has already returned and abandoned the channel, G2 blocks forever on the channel send, leaking the goroutine.

### Recommended Repair
Make resCh a buffered channel of size 1 (`resCh := make(chan string, 1)`), or use context-aware select inside the spawned goroutine when sending.

---

## Package `b12_slicealias` — **VULNERABLE**
- **Ground Truth:** `BUGGY` | **Detected:** `True`
- **Bug Category:** Data Race
- **Violated Rely-Guarantee Contract:** ProcessPartitions processes buffer partitions concurrently without violating memory safety
- **Empirical Test Witnessed Bug:** `True` (Compiled: `True`)

### Adversarial Interleaving Schedule
1. **[G1 (CallerSplitBuffer)]** Calls ProcessPartitions(data) with data = []int{1, 2, 3}
2. **[G2 (ProcessPartitions)]** Slices left := buf[:1] (len 1, cap 3) and right := buf[1:2] (len 1, cap 2)
3. **[G3 (First goroutine)]** Executes left = append(left, 99). Since len(left) is 1 and capacity is 3, append writes 99 into buf[1], resizing the shared slice's length.
4. **[G4 (Second goroutine)]** Executes right[0] = 42. Concurrently writes to buf[1] (or adjacent memory depending on slicing), causing a data race on underlying memory elements.

### Recommended Repair
Avoid slicing overlapping or shared underlying arrays without synchronization, or use distinct allocations / proper synchronization mutexes when modifying shared backing arrays.

---

## Package `b13_doubletransfer` — **VULNERABLE**
- **Ground Truth:** `BUGGY` | **Detected:** `True`
- **Bug Category:** Atomicity Violation
- **Violated Rely-Guarantee Contract:** Transfer: Atomic money transfer between distinct vaults without creation or destruction of funds. Split-lock gap exists between src.Withdraw(amt) and dst.Deposit(amt) in Transfer().
- **Empirical Test Witnessed Bug:** `False` (Compiled: `True`)

### Adversarial Interleaving Schedule
1. **[G1]** Transfer(src, dst, 100) calls src.Withdraw(100), locks src.mu, decrements src.balance, unlocks src.mu, returns true.
2. **[G2]** CallerAuditConservation(src, dst) or concurrent transfer reads intermediate state where funds have left src but not yet arrived at dst, violating the global conservation invariant.
3. **[G1]** Transfer resumes and calls dst.Deposit(100), locking dst.mu and incrementing dst.balance.

### Recommended Repair
To make Transfer atomic across both vaults, acquire both locks in a consistent order (e.g., ordered by memory address to avoid deadlocks) or introduce a higher-level mutex/transaction mechanism: 

func Transfer(src, dst *Vault, amt int) bool {
	if src == dst {
		return false
	}
	// Lock both in address order to prevent deadlock
	var first, second *Vault
	if &src.mu < &dst.mu {
		first, second = src, dst
	} else {
		first, second = dst, src
	}
	first.mu.Lock()
	defer first.mu.Unlock()
	second.mu.Lock()
	defer second.mu.Unlock()

	if src.balance < amt {
		return false
	}
	src.balance -= amt
	dst.balance += amt
	return true
}

---

## Package `b14_poolpoison` — **VULNERABLE**
- **Ground Truth:** `BUGGY` | **Detected:** `True`
- **Bug Category:** Atomicity Violation
- **Violated Rely-Guarantee Contract:** Premature pool/resource release before final field mutation (check-then-act / split-lock gap between Release and subsequent mutations on the returned buffer)
- **Empirical Test Witnessed Bug:** `False` (Compiled: `True`)

### Adversarial Interleaving Schedule
1. **[G1]** CallerHandleSession calls p.Acquire(user), gets buf, then immediately calls p.Release(buf)
2. **[G1]** Release adds buf back to p.free under p.mu
3. **[G2]** Another goroutine calls p.Acquire(otherUser), pops buf from p.free, locks buf.mu, and modifies buf.owner and buf.dirty
4. **[G1]** G1 resumes after Release and executes buf.mu.Lock(), buf.dirty = true, mutating a buffer that is now concurrently owned and used by G2

### Recommended Repair
Perform all mutations on the SessionBuf (such as setting dirty and inspecting/modifying fields) while still holding exclusive access or before releasing the buffer back to the pool. In CallerHandleSession, set buf.dirty = true BEFORE calling p.Release(buf).

---

## Package `b15_oncefallback` — **VULNERABLE**
- **Ground Truth:** `BUGGY` | **Detected:** `True`
- **Bug Category:** Atomicity Violation
- **Violated Rely-Guarantee Contract:** sync.Once caching transient errors permanently, preventing future successful initialization attempts.
- **Empirical Test Witnessed Bug:** `False` (Compiled: `True`)

### Adversarial Interleaving Schedule
1. **[G1]** Calls m.Init(true), enters m.once.Do and sets m.err = errors.New("dial timeout")
2. **[G2]** Calls m.Init(false), m.once.Do skips execution because once has already run (due to G1's failure), returns m.conn ("") and m.err ("dial timeout") permanently

### Recommended Repair
Remove sync.Once or implement a retry loop using sync.Mutex where initialization repeats until m.err == nil.

---

## Package `b16_subpubrace` — **VULNERABLE**
- **Ground Truth:** `BUGGY` | **Detected:** `True`
- **Bug Category:** Atomicity Violation
- **Violated Rely-Guarantee Contract:** CallerWatchFromCurrent expects to observe a consistent snapshot where any event published after LatestVersion() returns is guaranteed to be delivered to the channel returned by Subscribe().
- **Empirical Test Witnessed Bug:** `True` (Compiled: `True`)

### Adversarial Interleaving Schedule
1. **[G1 (CallerWatchFromCurrent)]** Calls b.LatestVersion() -> acquires mu, reads version = 1, releases mu.
2. **[G2 (Publisher)]** Calls b.PublishNext() -> acquires mu, increments version to 2, broadcasts version 2 to existing subs (none yet), releases mu.
3. **[G1 (CallerWatchFromCurrent)]** Calls b.Subscribe() -> acquires mu, appends new channel ch to b.subs, releases mu.

### Recommended Repair
Combine LatestVersion and Subscribe into a single atomic method under one lock acquisition, e.g., func (b *EventBroker) WatchFromCurrent() (int, chan int) { b.mu.Lock(); defer b.mu.Unlock(); ch := make(chan int, 1); b.subs = append(b.subs, ch); return b.version, ch }

---

## Package `b17_timerreset` — **VULNERABLE**
- **Ground Truth:** `BUGGY` | **Detected:** `True`
- **Bug Category:** Atomicity Violation
- **Violated Rely-Guarantee Contract:** time.Timer.Reset() called without draining timer.C when Stop() returns false can cause Reset() to fail to reset properly or channel to be out of sync.
- **Empirical Test Witnessed Bug:** `False` (Compiled: `True`)

### Adversarial Interleaving Schedule
1. **[G1]** Calls w.Kick(d) which fires timer and successfully stops it before it's read, or timer expires naturally.
2. **[G2]** Calls w.Kick(d) where w.timer.Stop() returns false because the timer has already fired and its channel contains an unread expiration value.
3. **[G2]** Executes w.timer.Reset(d) without draining the stale value from w.timer.C, leading to potential premature expiration or protocol violation.

### Recommended Repair
func (w *Watchdog) Kick(d time.Duration) {
	w.mu.Lock()
	defer w.mu.Unlock()
	if !w.timer.Stop() {
		select {
		case <-w.timer.C:
		default:
		}
	}
	w.timer.Reset(d)
}

---

## Package `b18_nestedrw` — **VULNERABLE**
- **Ground Truth:** `BUGGY` | **Detected:** `True`
- **Bug Category:** Deadlock
- **Violated Rely-Guarantee Contract:** Reentrant RWMutex.RLock() calls that deadlock when a concurrent writer calls Lock()
- **Empirical Test Witnessed Bug:** `True` (Compiled: `True`)

### Adversarial Interleaving Schedule
1. **[G1]** Calls ReadWithFallback, acquires r.mu.RLock() at line 21.
2. **[G1]** Calls r.lookupInternal(fallback) inside ReadWithFallback while holding r.mu.RLock().
3. **[G1]** Attempts to acquire r.mu.RLock() inside lookupInternal (line 15) while already holding r.mu (reentrant RLock).
4. **[G2]** Attempts to call Update, requesting r.mu.Lock(). In Go, sync.RWMutex is NOT reentrant. If a pending Writer (G2) is waiting for the lock, a goroutine (G1) holding an RLock that tries to recursively acquire RLock will block behind the writer, causing a permanent deadlock.

### Recommended Repair
Remove the inner locking from lookupInternal and make it an unexported helper that expects the caller to already hold r.mu. For example:

func (r *Registry) lookupInternal(k string) int {
	return r.items[k]
}

And ensure ReadWithFallback and lookupInternal do not nest RLock calls.

---

## Package `c01_safebank` — **SAFE (VERIFIED)**
- **Ground Truth:** `SAFE` | **Detected:** `False`
- **Bug Category:** None
- **Violated Rely-Guarantee Contract:** None
- **Empirical Test Witnessed Bug:** `False` (Compiled: `True`)

### Adversarial Interleaving Schedule

### Recommended Repair
None

---

## Package `c02_safepool` — **SAFE (VERIFIED)**
- **Ground Truth:** `SAFE` | **Detected:** `False`
- **Bug Category:** None
- **Violated Rely-Guarantee Contract:** None
- **Empirical Test Witnessed Bug:** `False` (Compiled: `False`)

### Adversarial Interleaving Schedule

### Recommended Repair
None

---

## Package `c03_epochcommit` — **SAFE (VERIFIED)**
- **Ground Truth:** `SAFE` | **Detected:** `False`
- **Bug Category:** None
- **Violated Rely-Guarantee Contract:** None
- **Empirical Test Witnessed Bug:** `False` (Compiled: `True`)

### Adversarial Interleaving Schedule

### Recommended Repair
The current implementation is safe because CallerOptimisticAdd correctly uses the epoch returned by Read as a version token for the CompareAndCommit operation, ensuring atomicity of the read-modify-write cycle despite the split-lock gap.

---

## Package `c04_actorloop` — **SAFE (VERIFIED)**
- **Ground Truth:** `SAFE` | **Detected:** `False`
- **Bug Category:** None
- **Violated Rely-Guarantee Contract:** None
- **Empirical Test Witnessed Bug:** `False` (Compiled: `True`)

### Adversarial Interleaving Schedule

### Recommended Repair
None

---

## Package `c05_cowatomic` — **SAFE (VERIFIED)**
- **Ground Truth:** `SAFE` | **Detected:** `False`
- **Bug Category:** None
- **Violated Rely-Guarantee Contract:** None
- **Empirical Test Witnessed Bug:** `False` (Compiled: `True`)

### Adversarial Interleaving Schedule

### Recommended Repair
None

---

## Package `c06_semctx` — **SAFE (VERIFIED)**
- **Ground Truth:** `SAFE` | **Detected:** `False`
- **Bug Category:** None
- **Violated Rely-Guarantee Contract:** None if safe
- **Empirical Test Witnessed Bug:** `False` (Compiled: `True`)

### Adversarial Interleaving Schedule

### Recommended Repair
None

---

## Package `c07_lockedhelper` — **SAFE (VERIFIED)**
- **Ground Truth:** `SAFE` | **Detected:** `False`
- **Bug Category:** None
- **Violated Rely-Guarantee Contract:** None
- **Empirical Test Witnessed Bug:** `False` (Compiled: `True`)

### Adversarial Interleaving Schedule

### Recommended Repair
None

---

## Package `c08_confinedworker` — **SAFE (VERIFIED)**
- **Ground Truth:** `SAFE` | **Detected:** `False`
- **Bug Category:** None
- **Violated Rely-Guarantee Contract:** None
- **Empirical Test Witnessed Bug:** `False` (Compiled: `True`)

### Adversarial Interleaving Schedule

### Recommended Repair
None

---
