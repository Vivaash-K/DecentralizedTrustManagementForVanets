from typing import Dict, List, Tuple
import math
from config import (
    NETWORK_LENGTH, NETWORK_WIDTH, MAX_V2V_RANGE,
    VEHICLE_MIN_VELOCITY, VEHICLE_MAX_VELOCITY,
    MAX_VEHICLES
)

class GyTARRouter:
    def __init__(self):
        self.junction_scores: Dict[Tuple[float, float], float] = {}
        self.route_cache: Dict[str, List[Dict[str, float]]] = {}

    def find_route(self, source_location: Dict[str, float],
                  destination_location: Dict[str, float],
                  vehicles: Dict[str, Dict],
                  traffic_data: Dict[str, float]) -> List[Dict[str, float]]:
        """
        Find the optimal route using GyTAR (Greedy Traffic Aware Routing) algorithm.
        
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
        
        # Initialize route
        current_pos = source_location.copy()
        route = [current_pos]
        
        while self._distance(current_pos, destination_location) > 100:  # Within 100m considered as reached
            # Find next junction
            next_junction = self._find_next_junction(
                current_pos,
                destination_location,
                vehicles,
                traffic_data
            )
            
            if not next_junction:
                break
                
            # Find path to next junction through vehicles
            path_to_junction = self._find_path_to_junction(
                current_pos,
                next_junction,
                vehicles
            )
            
            route.extend(path_to_junction)
            current_pos = next_junction
        
        route.append(destination_location)
        self.route_cache[route_key] = route
        return route

    def _find_next_junction(self, current_pos: Dict[str, float],
                          destination: Dict[str, float],
                          vehicles: Dict[str, Dict],
                          traffic_data: Dict[str, float]) -> Dict[str, float]:
        """Find the next best junction based on traffic and direction."""
        best_score = float('-inf')
        best_junction = None
        
        # Get potential junctions (simplified for this implementation)
        potential_junctions = self._get_potential_junctions(current_pos)
        
        for junction in potential_junctions:
            score = self._calculate_junction_score(
                current_pos,
                junction,
                destination,
                vehicles,
                traffic_data
            )
            
            if score > best_score:
                best_score = score
                best_junction = junction
        
        return best_junction

    def _get_potential_junctions(self, current_pos: Dict[str, float]) -> List[Dict[str, float]]:
        """Get list of potential junctions within range."""
        # Simplified implementation: Create a grid of junctions
        junctions = []
        grid_size = 500  # meters between junctions
        
        for x in range(0, NETWORK_LENGTH, grid_size):
            for y in range(0, NETWORK_WIDTH, grid_size):
                if self._distance(current_pos, {'x': x, 'y': y}) <= MAX_V2V_RANGE:
                    junctions.append({'x': x, 'y': y})
        
        return junctions

    def _calculate_junction_score(self, current_pos: Dict[str, float],
                                junction: Dict[str, float],
                                destination: Dict[str, float],
                                vehicles: Dict[str, Dict],
                                traffic_data: Dict[str, float]) -> float:
        """Calculate score for a potential junction."""
        # Direction score (progress towards destination)
        current_to_dest = self._distance(current_pos, destination)
        junction_to_dest = self._distance(junction, destination)
        direction_score = (current_to_dest - junction_to_dest) / current_to_dest
        
        # Traffic density score
        density_score = self._calculate_traffic_density(junction, vehicles)
        
        # Congestion score
        congestion_score = 1 - traffic_data.get('congestion_level', 0)
        
        # Weighted combination
        return (0.4 * direction_score +
                0.4 * density_score +
                0.2 * congestion_score)

    def _calculate_traffic_density(self, junction: Dict[str, float],
                                 vehicles: Dict[str, Dict]) -> float:
        """Calculate traffic density around a junction."""
        vehicles_in_range = 0
        # Use 10% of max vehicles as normalization factor
        max_vehicles = MAX_VEHICLES * 0.1  
        
        for vehicle_data in vehicles.values():
            if self._distance(junction, vehicle_data['location']) <= MAX_V2V_RANGE:
                vehicles_in_range += 1
        
        return min(1.0, vehicles_in_range / max_vehicles)

    def _find_path_to_junction(self, start: Dict[str, float],
                             junction: Dict[str, float],
                             vehicles: Dict[str, Dict]) -> List[Dict[str, float]]:
        """Find a path to the junction through intermediate vehicles."""
        path = [start]
        current = start
        
        while self._distance(current, junction) > 100:  # Within 100m considered as reached
            next_hop = self._find_next_vehicle_hop(current, junction, vehicles)
            if not next_hop:
                break
            path.append(next_hop)
            current = next_hop
        
        path.append(junction)
        return path

    def _find_next_vehicle_hop(self, current: Dict[str, float],
                             target: Dict[str, float],
                             vehicles: Dict[str, Dict]) -> Dict[str, float]:
        """Find next vehicle hop towards target."""
        best_score = float('-inf')
        best_next_hop = None
        
        for vehicle_data in vehicles.values():
            if self._is_forward_progress(current, vehicle_data['location'], target):
                score = self._calculate_vehicle_hop_score(
                    current,
                    vehicle_data['location'],
                    target,
                    vehicle_data['speed']
                )
                if score > best_score:
                    best_score = score
                    best_next_hop = vehicle_data['location']
        
        return best_next_hop

    def _calculate_vehicle_hop_score(self, current: Dict[str, float],
                                   next_hop: Dict[str, float],
                                   target: Dict[str, float],
                                   speed: float) -> float:
        """Calculate score for potential next vehicle hop."""
        # Progress towards target
        progress = (self._distance(current, target) -
                   self._distance(next_hop, target))
        
        # Speed factor
        speed_factor = (speed - VEHICLE_MIN_VELOCITY) / (VEHICLE_MAX_VELOCITY - VEHICLE_MIN_VELOCITY)
        
        return 0.7 * progress + 0.3 * speed_factor

    def _is_forward_progress(self, current: Dict[str, float],
                           next_hop: Dict[str, float],
                           target: Dict[str, float]) -> bool:
        """Check if next hop makes progress towards target."""
        current_dist = self._distance(current, target)
        next_dist = self._distance(next_hop, target)
        return next_dist < current_dist

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