from typing import Dict, List, Set, Tuple
import time
import math
from config import *

class AODVRouter:
    def __init__(self):
        self.routing_table: Dict[str, Dict] = {}
        self.sequence_numbers: Dict[str, int] = {}
        self.rreq_buffer: Set[str] = set()
        self.route_cache: Dict[str, List[Dict[str, float]]] = {}
        self.last_cleanup = time.time()

    def find_route(self, source_location: Dict[str, float],
                  destination_location: Dict[str, float],
                  vehicles: Dict[str, Dict],
                  traffic_data: Dict[str, float]) -> List[Dict[str, float]]:
        """
        Find route using AODV (Ad hoc On-Demand Distance Vector) routing protocol.
        
        Arguments:
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
            if self._is_route_valid(self.route_cache[route_key], vehicles):
                return self.route_cache[route_key]
            else:
                del self.route_cache[route_key]
        
        # Initialize route discovery
        route = self._discover_route(source_location, destination_location, vehicles)
        
        if route:
            self.route_cache[route_key] = route
            return route
        
        # If no route found, return direct path
        return [source_location, destination_location]

    def _discover_route(self, source: Dict[str, float],
                       destination: Dict[str, float],
                       vehicles: Dict[str, Dict]) -> List[Dict[str, float]]:
        """Perform AODV route discovery."""
        # Generate RREQ ID
        rreq_id = f"{source['x']},{source['y']}-{time.time()}"
        
        # Initialize discovery
        discovered_routes: Dict[str, List[Dict[str, float]]] = {}
        visited: Set[str] = set()
        
        # Start with source
        queue = [(source, [source])]
        visited.add(self._location_to_key(source))
        
        while queue:
            current, path = queue.pop(0)
            
            # Check if destination is in range
            if self._distance(current, destination) <= MAX_V2V_RANGE:
                path.append(destination)
                discovered_routes[self._calculate_route_key(path)] = path
                continue
            
            # Find neighbors
            for vehicle_id, vehicle_data in vehicles.items():
                vehicle_loc = vehicle_data['location']
                vehicle_key = self._location_to_key(vehicle_loc)
                
                if (vehicle_key not in visited and 
                    self._distance(current, vehicle_loc) <= MAX_V2V_RANGE):
                    visited.add(vehicle_key)
                    new_path = path + [vehicle_loc]
                    queue.append((vehicle_loc, new_path))
        
        # Select best discovered route
        return self._select_best_route(discovered_routes, vehicles)

    def _select_best_route(self, routes: Dict[str, List[Dict[str, float]]],
                          vehicles: Dict[str, Dict]) -> List[Dict[str, float]]:
        """Select the best route from discovered routes."""
        if not routes:
            return []
        
        best_score = float('-inf')
        best_route = None
        
        for route in routes.values():
            score = self._calculate_route_score(route, vehicles)
            if score > best_score:
                best_score = score
                best_route = route
        
        return best_route

    def _calculate_route_score(self, route: List[Dict[str, float]],
                             vehicles: Dict[str, Dict]) -> float:
        """Calculate score for a route based on stability and hop count."""
        if len(route) < 2:
            return float('-inf')
        
        # Hop count factor (fewer hops is better)
        hop_factor = 1.0 / (len(route) - 1)
        
        # Route stability factor
        stability_score = self._calculate_route_stability(route, vehicles)
        
        # Combined score
        return 0.4 * hop_factor + 0.6 * stability_score

    def _calculate_route_stability(self, route: List[Dict[str, float]],
                                 vehicles: Dict[str, Dict]) -> float:
        """Calculate route stability based on vehicle positions and velocities."""
        stability_scores = []
        
        for i in range(len(route) - 1):
            current = route[i]
            next_hop = route[i + 1]
            
            # Find vehicles near these points
            current_vehicle = self._find_nearest_vehicle(current, vehicles)
            next_vehicle = self._find_nearest_vehicle(next_hop, vehicles)
            
            if current_vehicle and next_vehicle:
                # Calculate link stability based on relative velocity and distance
                stability = self._calculate_link_stability(
                    current_vehicle['speed'],
                    next_vehicle['speed'],
                    self._distance(current, next_hop)
                )
                stability_scores.append(stability)
        
        return min(stability_scores) if stability_scores else 0.0

    def _find_nearest_vehicle(self, location: Dict[str, float],
                            vehicles: Dict[str, Dict]) -> Dict:
        """Find the nearest vehicle to a location."""
        nearest = None
        min_distance = float('inf')
        
        for vehicle_data in vehicles.values():
            distance = self._distance(location, vehicle_data['location'])
            if distance < min_distance:
                min_distance = distance
                nearest = vehicle_data
        
        return nearest

    def _calculate_link_stability(self, speed1: float, speed2: float,
                                distance: float) -> float:
        """Calculate stability of a link between two vehicles."""
        # Normalize speeds
        speed1_norm = (speed1 - VEHICLE_MIN_VELOCITY) / (VEHICLE_MAX_VELOCITY - VEHICLE_MIN_VELOCITY)
        speed2_norm = (speed2 - VEHICLE_MIN_VELOCITY) / (VEHICLE_MAX_VELOCITY - VEHICLE_MIN_VELOCITY)
        
        # Relative speed factor (lower is better)
        speed_diff = abs(speed1_norm - speed2_norm)
        speed_factor = 1 - speed_diff
        
        # Distance factor (closer is better, but not too close)
        distance_factor = 1 - (distance / MAX_V2V_RANGE)
        
        return 0.5 * speed_factor + 0.5 * distance_factor

    def _is_route_valid(self, route: List[Dict[str, float]],
                       vehicles: Dict[str, Dict]) -> bool:
        """Check if a cached route is still valid."""
        for i in range(len(route) - 1):
            current = route[i]
            next_hop = route[i + 1]
            
            # Check if there are any vehicles that can maintain this link
            valid_link = False
            for vehicle_data in vehicles.values():
                if (self._distance(current, vehicle_data['location']) <= MAX_V2V_RANGE and
                    self._distance(next_hop, vehicle_data['location']) <= MAX_V2V_RANGE):
                    valid_link = True
                    break
            
            if not valid_link:
                return False
        
        return True

    @staticmethod
    def _distance(point1: Dict[str, float], point2: Dict[str, float]) -> float:
        """Calculate Euclidean distance between two points."""
        return math.sqrt(
            (point1['x'] - point2['x'])**2 +
            (point1['y'] - point2['y'])**2
        )

    @staticmethod
    def _location_to_key(location: Dict[str, float]) -> str:
        """Convert location to string key."""
        return f"{location['x']},{location['y']}"

    @staticmethod
    def _calculate_route_key(route: List[Dict[str, float]]) -> str:
        """Calculate unique key for a route."""
        return '-'.join(f"{point['x']},{point['y']}" for point in route)

    def cleanup_old_entries(self):
        """Clean up old routing entries and RREQ buffer."""
        current_time = time.time()
        if current_time - self.last_cleanup >= 60:  # Cleanup every minute
            self.rreq_buffer.clear()
            self.route_cache.clear()
            self.last_cleanup = current_time 