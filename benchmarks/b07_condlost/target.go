package b07_condlost

import "sync"

type TaskQueue struct {
	mu    sync.Mutex
	cond  *sync.Cond
	items []int
}

func NewTaskQueue() *TaskQueue {
	q := &TaskQueue{}
	q.cond = sync.NewCond(&q.mu)
	return q
}

func (q *TaskQueue) Enqueue(item int) {
	q.mu.Lock()
	q.items = append(q.items, item)
	q.mu.Unlock()
	q.cond.Signal()
}

func (q *TaskQueue) Dequeue() int {
	q.mu.Lock()
	defer q.mu.Unlock()
	if len(q.items) == 0 {
		q.cond.Wait()
	}
	item := q.items[0]
	q.items = q.items[1:]
	return item
}

func CallerProcessBatch(q *TaskQueue, id int) int {
	q.Enqueue(id)
	return q.Dequeue()
}
