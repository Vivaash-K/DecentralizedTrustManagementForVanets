from typing import Dict, List, Tuple
import math
from config import *

class TMRRouter:
    def __init__(self):
        self.route_cache: Dict[str, List[Dict[str, float]]] = {}
        self.message_history: Dict[str, float] = {}

    def find_route(self, source_location: Dict[str, float],
                  destination_location: Dict[str, float],
                  vehicles: Dict[str, Dict],
                  traffic_data: Dict[str, float]) -> List[Dict[str, float]]:
        """
        Find the optimal route using Traffic Message Routing algorithm.
        
        Args:
            source_location: Current vehicle location
            destination_location: Target location
            vehicles: Dictionary of nearby vehicles and their data
            traffic_data: Current traffic conditions
            
        Returns:
            List of waypoints for the route
        """
        route_key = f"{source_location['x']},{source_location['y']}->{destination_location['x']},{destination_location['y']}"
        
        # Check route cache first
        if route_key in self.route_cache:
            return self.route_cache[route_key]
        
        # Initialize parameters
        current_pos = source_location.copy()
        route = [current_pos]
        
        while self._distance(current_pos, destination_location) > 100:  # Within 100m considered as reached
            next_hop = self._find_next_hop(current_pos, destination_location, vehicles, traffic_data)
            if not next_hop:
                break
            route.append(next_hop)
            current_pos = next_hop
        
        route.append(destination_location)
        self.route_cache[route_key] = route
        return route

    def _find_next_hop(self, current_pos: Dict[str, float],
                      destination: Dict[str, float],
                      vehicles: Dict[str, Dict],
                      traffic_data: Dict[str, float]) -> Dict[str, float]:
        """Find the next hop based on traffic density and direction."""
        best_score = float('-inf')
        best_next_hop = None
        
        for vehicle_id, vehicle_data in vehicles.items():
            if self._is_forward_progress(current_pos, vehicle_data['location'], destination):
                score = self._calculate_hop_score(
                    current_pos,
                    vehicle_data['location'],
                    destination,
                    vehicle_data['speed'],
                    traffic_data.get('congestion_level', 0)
                )
                if score > best_score:
                    best_score = score
                    best_next_hop = vehicle_data['location']
        
        return best_next_hop

    def _is_forward_progress(self, current: Dict[str, float],
                           next_hop: Dict[str, float],
                           destination: Dict[str, float]) -> bool:
        """Check if next hop makes progress towards destination."""
        current_dist = self._distance(current, destination)
        next_dist = self._distance(next_hop, destination)
        return next_dist < current_dist

    def _calculate_hop_score(self, current: Dict[str, float],
                           next_hop: Dict[str, float],
                           destination: Dict[str, float],
                           speed: float,
                           congestion: float) -> float:
        """Calculate score for potential next hop."""
        # Distance progress factor
        progress = (self._distance(current, destination) - 
                   self._distance(next_hop, destination))
        
        # Speed factor (normalized)
        speed_factor = (speed - VEHICLE_MIN_VELOCITY) / (VEHICLE_MAX_VELOCITY - VEHICLE_MIN_VELOCITY)
        
        # Congestion penalty
        congestion_penalty = 1 - congestion
        
        # Combined score with weights
        return (0.5 * progress + 
                0.3 * speed_factor + 
                0.2 * congestion_penalty)

    @staticmethod
    def _distance(point1: Dict[str, float], point2: Dict[str, float]) -> float:
        """Calculate Euclidean distance between two points."""
        return math.sqrt(
            (point1['x'] - point2['x'])**2 +
            (point1['y'] - point2['y'])**2
        )

    def update_traffic(self, traffic_data: Dict[str, float]):
        """Update traffic information and clear old cache entries."""
        # Clear route cache if traffic conditions change significantly
        if len(self.route_cache) > 100:  # Prevent unlimited growth
            self.route_cache.clear() 