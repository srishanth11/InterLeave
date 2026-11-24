package b02_seat

import "sync"

type SeatMap struct {
	mu    sync.Mutex
	seats map[int]string
}

func NewSeatMap() *SeatMap { return &SeatMap{seats: make(map[int]string)} }

func (s *SeatMap) IsFree(seat int) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	_, taken := s.seats[seat]
	return !taken
}

func (s *SeatMap) Book(seat int, passenger string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.seats[seat] = passenger
}

func Reserve(s *SeatMap, seat int, passenger string) bool {
	if s.IsFree(seat) {
		s.Book(seat, passenger)
		return true
	}
	return false
}

func CallerCheckoutSeat(s *SeatMap, seat int, passenger string) bool {
	return Reserve(s, seat, passenger)
}
