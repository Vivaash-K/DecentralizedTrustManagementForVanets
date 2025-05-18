import socket
import json
import time
import random
import threading
import math
import sys
from typing import Dict, List, Set, Tuple, Any, Optional
from config import *

class Vehicle:
    def __init__(self, vehicle_id: str, initial_x: float, initial_y: float):
        self.id = vehicle_id
        self.location = {'x': initial_x, 'y': initial_y}
        self.speed = random.uniform(VEHICLE_MIN_VELOCITY, VEHICLE_MAX_VELOCITY)
        self.direction = random.uniform(0, 360)
        self.trust_score = 1.0
        self.neighbors: Dict[str, dict] = {}
        self.rsu_connections: Dict[str, dict] = {}
        self.is_malicious = False
        self.start_time = None  # Will be set when simulation starts
        
        # Communication setup
        self._setup_socket()
        
        # Start listening thread
        self.running = True
        self.listen_thread = threading.Thread(target=self._listen)
        self.listen_thread.daemon = True
        self.listen_thread.start()

    def _setup_socket(self):
        """Setup UDP socket for communication."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind(('localhost', 0))  # Random available port
            self.port = self.socket.getsockname()[1]
        except Exception as e:
            print(f"Socket setup error for vehicle {self.id}: {str(e)}")
            self.socket = None
            self.port = None

    def _log_communication(self, message: str):
        """Log vehicle communication data."""
        print(f"[{time.strftime('%H:%M:%S')}] Vehicle {self.id} at ({self.location['x']:.1f}, {self.location['y']:.1f}): {message}", flush=True)

    def _listen(self):
        """Listen for incoming messages."""
        while self.running and self.socket:
            try:
                data, addr = self.socket.recvfrom(4096)
                message = json.loads(data.decode())
                self._handle_message(message, addr)
            except Exception as e:
                if self.running:  # Only print error if we're supposed to be running
                    print(f"Vehicle {self.id} error: {e}")
                break

    def _handle_message(self, message: Dict, addr: Tuple[str, int]):
        """Handle incoming messages."""
        msg_type = message.get('type')
        sender = message.get('vehicle_id', message.get('rsu_id', 'Unknown'))
        
        if msg_type == 'beacon':
            # Update neighbor information
            sender_id = message['vehicle_id']
            self.neighbors[sender_id] = {
                'location': message['location'],
                'speed': message['speed'],
                'direction': message['direction'],
                'last_seen': time.time()
            }
            self._log_communication(
                f"Received beacon from V_{sender_id} at "
                f"({message['location']['x']:.1f}, {message['location']['y']:.1f})"
            )
        
        elif msg_type == 'rsu_beacon':
            # Update RSU connection
            rsu_id = message['rsu_id']
            self.rsu_connections[rsu_id] = {
                'location': message['location'],
                'last_seen': time.time()
            }
            self._log_communication(
                f"Received RSU beacon from {rsu_id} - "
                f"Traffic: {message['traffic_data']['vehicle_count']} vehicles, "
                f"Avg Speed: {message['traffic_data']['average_speed']:.1f} km/h"
            )
        
        elif msg_type == 'accident_alert':
            # Process accident information and decide route change
            self._log_communication(f"Received accident alert from {sender}")
            self._process_accident_alert(message)

    def broadcast_beacon(self):
        """Broadcast vehicle information to neighbors."""
        try:
            # Get accident visibility based on vehicle's location
            can_see_accident = self._check_accident_visibility()
            
            if self.is_malicious:
                # Malicious vehicles intentionally broadcast false data
                # Choose behavior type based on vehicle_id to maintain consistency
                behavior_type = hash(self.id) % 3  # 0, 1, or 2
                
                if behavior_type == 0:
                    # Consistently report impossible speeds
                    false_speed = VEHICLE_MAX_VELOCITY * 2.5
                    false_location = self.location.copy()
                elif behavior_type == 1:
                    # Consistently report large position jumps
                    false_location = {
                        'x': self.location['x'] + 400 * math.cos(time.time()),
                        'y': self.location['y'] + 400 * math.sin(time.time())
                    }
                    false_speed = self.speed
                else:  # behavior_type == 2
                    # Consistently report positions outside bounds
                    false_location = {
                        'x': -50 if time.time() % 2 < 1 else NETWORK_LENGTH + 50,
                        'y': self.location['y']
                    }
                    false_speed = self.speed
                
                # For accident visibility, report opposite of nearby vehicles
                nearby_reports = self._get_nearby_vehicles_accident_reports()
                false_accident_visibility = not nearby_reports if nearby_reports is not None else not can_see_accident
                
                message = {
                    'type': 'beacon',
                    'vehicle_id': self.id,
                    'location': false_location,
                    'speed': false_speed,
                    'direction': self.direction,
                    'timestamp': time.time(),
                    'sees_accident': false_accident_visibility
                }
                
                self._log_communication(
                    f"[MALICIOUS] Broadcasting false beacon - "
                    f"Speed: {false_speed:.1f} km/h, "
                    f"Pos: ({false_location['x']:.1f}, {false_location['y']:.1f}), "
                    f"Sees accident: {false_accident_visibility}"
                )
            else:
                message = {
                    'type': 'beacon',
                    'vehicle_id': self.id,
                    'location': self.location,
                    'speed': self.speed,
                    'direction': self.direction,
                    'timestamp': time.time(),
                    'sees_accident': can_see_accident
                }
                self._log_communication(
                    f"Broadcasting beacon (speed: {self.speed:.1f} km/h, "
                    f"sees accident: {can_see_accident})"
                )
            
            self._broadcast(message)
        except Exception as e:
            self._log_communication(f"Error in broadcast_beacon: {str(e)}")

    def _check_accident_visibility(self) -> bool:
        """Check if vehicle can see an accident based on its location."""
        # Get accident location from config
        accident_loc = ACCIDENT_LOCATION
        
        # Calculate distance to accident
        distance = math.sqrt(
            (self.location['x'] - accident_loc['x'])**2 +
            (self.location['y'] - accident_loc['y'])**2
        )
        
        # Vehicle can see accident if within 200m and accident has occurred
        # (accident occurs after 10 seconds of simulation)
        if self.start_time is None:
            return False  # If start time not set, assume no accident
            
        simulation_time = time.time() - self.start_time
        accident_occurred = simulation_time > 10
        
        return distance <= 200 and accident_occurred

    def _get_nearby_vehicles_accident_reports(self) -> Optional[bool]:
        """Get the majority accident report from nearby vehicles."""
        accident_reports = []
        
        for neighbor_id, neighbor_data in self.neighbors.items():
            # Only consider recent reports (within last 2 seconds)
            if (time.time() - neighbor_data.get('last_seen', 0) <= 2 and
                'sees_accident' in neighbor_data):
                accident_reports.append(neighbor_data['sees_accident'])
        
        if accident_reports:
            # Return the majority vote
            return sum(accident_reports) > len(accident_reports) / 2
        
        return None

    def _broadcast(self, message: Dict):
        """Send message to all neighbors within range."""
        if not self.socket:
            return
            
        data = json.dumps(message).encode()
        # Broadcast to known neighbors
        for neighbor_id, neighbor in self.neighbors.items():
            if self._is_in_range(neighbor['location']):
                try:
                    self.socket.sendto(data, ('localhost', neighbor['port']))
                    self._log_communication(f"Sent message to {neighbor_id}: {message['type']}")
                except Exception as e:
                    self._log_communication(f"Error sending to neighbor {neighbor_id}: {e}")

    def _is_in_range(self, target_location: Dict[str, float]) -> bool:
        """Check if target is within communication range."""
        distance = math.sqrt(
            (self.location['x'] - target_location['x'])**2 +
            (self.location['y'] - target_location['y'])**2
        )
        return distance <= MAX_V2V_RANGE

    def update_position(self, timestep: float):
        """Update vehicle position based on speed and direction."""
        # Convert speed from km/h to m/s
        speed_ms = self.speed * 1000 / 3600
        
        if self.is_malicious:
            # Malicious vehicles intentionally report false data:
            # 1. Sudden impossible speed changes
            # 2. Teleporting (large position jumps)
            # 3. Moving outside network bounds
            malicious_behavior = random.choice([1, 2, 3])
            
            if malicious_behavior == 1:
                # Sudden extreme speed change
                self.speed = random.uniform(VEHICLE_MAX_VELOCITY * 2, VEHICLE_MAX_VELOCITY * 3)
                speed_ms = self.speed * 1000 / 3600
            elif malicious_behavior == 2:
                # Teleport to random location
                self.location['x'] += random.uniform(200, 500) * random.choice([-1, 1])
                self.location['y'] += random.uniform(200, 500) * random.choice([-1, 1])
            else:
                # Move outside network bounds
                if random.random() < 0.5:
                    self.location['x'] = -random.uniform(100, 200)
                else:
                    self.location['x'] = NETWORK_LENGTH + random.uniform(100, 200)
        
        # Update position
        self.location['x'] += speed_ms * math.cos(math.radians(self.direction)) * timestep
        self.location['y'] += speed_ms * math.sin(math.radians(self.direction)) * timestep
        
        # Keep non-malicious vehicles within network boundaries
        if not self.is_malicious:
            self.location['x'] = max(0, min(self.location['x'], NETWORK_LENGTH))
            self.location['y'] = max(0, min(self.location['y'], NETWORK_WIDTH))

    def process_accident_decision(self, num_vehicles_ahead: int, 
                                num_staying_on_route: int) -> bool:
        """Decide whether to stay on current route or take alternate route."""
        # Simple decision based on ratio of vehicles staying on route
        ratio = num_staying_on_route / num_vehicles_ahead if num_vehicles_ahead > 0 else 0
        return ratio < 0.5  # Take alternate route if more than 50% are staying

    def stop(self):
        """Stop the vehicle's communication threads."""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.socket = None

    def __del__(self):
        self.stop()

    def set_simulation_start_time(self, start_time: float):
        """Set the simulation start time for the vehicle."""
        self.start_time = start_time 