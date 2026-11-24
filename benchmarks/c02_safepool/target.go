package c02_safepool

import "sync"

type Job struct{ ID int }

func SafeWorkerPool(jobs <-chan Job, results chan<- int, wg *sync.WaitGroup) {
	defer wg.Done()
	for job := range jobs {
		results <- job.ID * 2
	}
}

func CallerRunPool(ids []int) int {
	jobs := make(chan Job, len(ids))
	results := make(chan int, len(ids))
	var wg sync.WaitGroup
	wg.Add(2)
	go SafeWorkerPool(jobs, results, &wg)
	go SafeWorkerPool(jobs, results, &wg)
	for _, id := range ids {
		jobs <- Job{ID: id}
	}
	close(jobs)
	wg.Wait()
	close(results)
	sum := 0
	for r := range results {
		sum += r
	}
	return sum
}
