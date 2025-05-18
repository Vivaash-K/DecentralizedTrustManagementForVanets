import socket
import json
import time
import threading
import math
import sys
from typing import Dict, List, Set, Tuple, Any
from config import (
    NETWORK_LENGTH, NETWORK_WIDTH, RSU_RADIUS, 
    VEHICLE_MIN_VELOCITY, VEHICLE_MAX_VELOCITY,
    MIN_VEHICLES, MAX_VEHICLES
)
from blockchain import Blockchain

class RSU:
    def __init__(self, rsu_id: str, x: float, y: float, blockchain: Blockchain):
        self.id = rsu_id
        self.location = {'x': x, 'y': y}
        self.blockchain = blockchain
        self.connected_vehicles: Dict[str, dict] = {}
        self.suspicious_vehicles: Set[str] = set()
        self.suspicious_count: Dict[str, int] = {}  # Track number of suspicious activities
        self.traffic_data: Dict[str, Any] = {
            'vehicle_count': 0,
            'average_speed': 0,
            'congestion_level': 0
        }
        
        # Communication setup
        self._setup_socket()
        
        # Start listening thread
        self.running = True
        self.listen_thread = threading.Thread(target=self._listen)
        self.listen_thread.daemon = True
        self.listen_thread.start()
        
        # Start periodic tasks
        self.beacon_thread = threading.Thread(target=self._periodic_tasks)
        self.beacon_thread.daemon = True
        self.beacon_thread.start()

    def _setup_socket(self):
        """Setup UDP socket for communication."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind(('localhost', 0))
            self.port = self.socket.getsockname()[1]
        except Exception as e:
            print(f"Socket setup error for RSU {self.id}: {str(e)}")
            self.socket = None
            self.port = None

    def _log_communication(self, message: str):
        """Log RSU communication data."""
        print(f"[{time.strftime('%H:%M:%S')}] RSU {self.id} at ({self.location['x']:.1f}, {self.location['y']:.1f}): {message}", flush=True)

    def _listen(self):
        """Listen for incoming messages from vehicles."""
        while self.running and self.socket:
            try:
                data, addr = self.socket.recvfrom(4096)
                message = json.loads(data.decode())
                self._handle_message(message, addr)
            except Exception as e:
                if self.running:  # Only print error if we're supposed to be running
                    print(f"RSU {self.id} error: {e}")
                break

    def _handle_message(self, message: Dict, addr: Tuple[str, int]):
        """Handle incoming messages from vehicles."""
        msg_type = message.get('type')
        sender = message.get('vehicle_id', 'Unknown')
        
        if msg_type == 'beacon':
            vehicle_id = message['vehicle_id']
            self._log_communication(
                f"Received beacon from {vehicle_id} at "
                f"({message['location']['x']:.1f}, {message['location']['y']:.1f}), "
                f"speed: {message['speed']:.1f} km/h"
            )
            self._update_vehicle_data(vehicle_id, message, addr)
        
        elif msg_type == 'accident_report':
            self._log_communication(f"Received accident report from {sender}")
            self._process_accident_report(message)
            self._broadcast_accident_alert(message)

    def _update_vehicle_data(self, vehicle_id: str, data: Dict, addr: Tuple[str, int]):
        """Update stored vehicle data and check for suspicious behavior."""
        current_time = time.time()
        
        # First, check if vehicle is already marked as malicious
        if vehicle_id in self.blockchain.get_malicious_vehicles():
            print(f"\n🚨 RSU {self.id}: Rejected data from known malicious vehicle {vehicle_id}")
            return

        if vehicle_id in self.connected_vehicles:
            prev_data = self.connected_vehicles[vehicle_id]
            time_diff = current_time - prev_data['timestamp']
            
            if time_diff > 0:
                # Initialize suspicious detection for this update
                is_suspicious = False
                suspicious_reasons = []
                
                # 1. Check for impossible speed
                if data['speed'] > VEHICLE_MAX_VELOCITY * 1.5:
                    is_suspicious = True
                    suspicious_reasons.append(f"Impossible speed: {data['speed']:.1f} km/h")
                
                # 2. Check for impossible movement
                max_distance = (prev_data['speed'] * 1000 / 3600) * time_diff * 1.2
                actual_distance = math.sqrt(
                    (data['location']['x'] - prev_data['location']['x'])**2 +
                    (data['location']['y'] - prev_data['location']['y'])**2
                )
                if actual_distance > max_distance:
                    is_suspicious = True
                    suspicious_reasons.append(f"Impossible movement: {actual_distance:.1f}m in {time_diff:.1f}s")
                
                # 3. Check for position outside bounds
                if (data['location']['x'] < -10 or data['location']['x'] > NETWORK_LENGTH + 10 or
                    data['location']['y'] < -10 or data['location']['y'] > NETWORK_WIDTH + 10):
                    is_suspicious = True
                    suspicious_reasons.append(f"Position outside bounds: ({data['location']['x']:.1f}, {data['location']['y']:.1f})")
                
                # 4. Check for inconsistent accident reporting
                if 'sees_accident' in data:
                    nearby_vehicles = self._get_nearby_vehicles(data['location'])
                    nearby_reports = [
                        v['sees_accident'] for v in nearby_vehicles.values()
                        if 'sees_accident' in v and v['timestamp'] > current_time - 2
                    ]
                    
                    if nearby_reports:
                        majority_report = sum(nearby_reports) > len(nearby_reports) / 2
                        if data['sees_accident'] != majority_report:
                            is_suspicious = True
                            suspicious_reasons.append(
                                f"Inconsistent accident report: reported {data['sees_accident']} "
                                f"while {len(nearby_reports)} nearby vehicles reported {majority_report}"
                            )
                
                if is_suspicious:
                    self.suspicious_count[vehicle_id] = self.suspicious_count.get(vehicle_id, 0) + 1
                    count = self.suspicious_count[vehicle_id]
                    
                    print(f"\n⚠️ RSU {self.id}: SUSPICIOUS ACTIVITY #{count} from {vehicle_id}")
                    print(f"Reasons: {', '.join(suspicious_reasons)}")
                    
                    if count >= 3:
                        print(f"\n🚨 RSU {self.id}: MARKING VEHICLE {vehicle_id} AS MALICIOUS")
                        print(f"Evidence: {count} suspicious activities detected")
                        self.blockchain.add_malicious_vehicle(vehicle_id)
                        if vehicle_id in self.connected_vehicles:
                            del self.connected_vehicles[vehicle_id]
                        return
        
        # Update vehicle data if not marked as malicious
        self.connected_vehicles[vehicle_id] = {
            **data,
            'timestamp': current_time,
            'port': addr[1]
        }

    def _get_nearby_vehicles(self, location: Dict[str, float], range_limit: float = 300) -> Dict[str, Dict]:
        """Get all vehicles within range_limit meters of the given location."""
        nearby = {}
        for vid, vdata in self.connected_vehicles.items():
            if vid not in self.blockchain.get_malicious_vehicles():
                distance = math.sqrt(
                    (location['x'] - vdata['location']['x'])**2 +
                    (location['y'] - vdata['location']['y'])**2
                )
                if distance <= range_limit:
                    nearby[vid] = vdata
        return nearby

    def _periodic_tasks(self):
        """Perform periodic tasks like sending beacons and updating traffic data."""
        last_malicious_report = 0
        while self.running:
            current_time = time.time()
            
            # Log malicious vehicles every 5 seconds if any exist
            if current_time - last_malicious_report >= 5:
                malicious = self.blockchain.get_malicious_vehicles()
                if malicious:
                    print(f"\n🚨 RSU {self.id}: Current Malicious Vehicles ({len(malicious)}):")
                    print(f"IDs: {', '.join(malicious)}")
                last_malicious_report = current_time
            
            self._broadcast_beacon()
            self._update_traffic_data()
            self.blockchain.record_rsu_data(
                self.id,
                list(self.connected_vehicles.keys()),
                self.traffic_data
            )
            time.sleep(1)

    def _broadcast_beacon(self):
        """Broadcast RSU beacon to all vehicles in range."""
        message = {
            'type': 'rsu_beacon',
            'rsu_id': self.id,
            'location': self.location,
            'traffic_data': self.traffic_data,
            'timestamp': time.time()
        }
        self._log_communication(
            f"Broadcasting beacon - Traffic Data: "
            f"{self.traffic_data['vehicle_count']} vehicles, "
            f"avg speed: {self.traffic_data['average_speed']:.1f} km/h, "
            f"congestion: {self.traffic_data['congestion_level']:.2f}"
        )
        self._broadcast(message)

    def _broadcast(self, message: Dict):
        """Send message to all connected vehicles."""
        if not self.socket:
            return
            
        data = json.dumps(message).encode()
        for vehicle_id, vehicle in self.connected_vehicles.items():
            # Only broadcast to non-malicious vehicles
            if (vehicle_id not in self.blockchain.get_malicious_vehicles() and 
                self._is_in_range(vehicle['location'])):
                try:
                    self.socket.sendto(data, ('localhost', vehicle['port']))
                    self._log_communication(f"Sent {message['type']} to vehicle {vehicle_id}")
                except Exception as e:
                    self._log_communication(f"Error sending to vehicle {vehicle_id}: {e}")

    def _is_in_range(self, target_location: Dict[str, float]) -> bool:
        """Check if target is within RSU range."""
        distance = math.sqrt(
            (self.location['x'] - target_location['x'])**2 +
            (self.location['y'] - target_location['y'])**2
        )
        return distance <= RSU_RADIUS

    def _update_traffic_data(self):
        """Update traffic statistics."""
        current_time = time.time()
        # Only consider non-malicious vehicles
        active_vehicles = {
            vid: data for vid, data in self.connected_vehicles.items()
            if (current_time - data['timestamp'] < 5 and  # Consider only recent data
                vid not in self.blockchain.get_malicious_vehicles())
        }
        
        if active_vehicles:
            avg_speed = sum(v['speed'] for v in active_vehicles.values()) / len(active_vehicles)
            self.traffic_data.update({
                'vehicle_count': len(active_vehicles),
                'average_speed': avg_speed,
                'congestion_level': self._calculate_congestion_level(len(active_vehicles), avg_speed)
            })

    def _calculate_congestion_level(self, vehicle_count: int, avg_speed: float) -> float:
        """Calculate congestion level (0-1) based on vehicle count and average speed."""
        speed_factor = 1 - (avg_speed - VEHICLE_MIN_VELOCITY) / (VEHICLE_MAX_VELOCITY - VEHICLE_MIN_VELOCITY)
        # Adjust count factor based on maximum possible vehicles
        count_factor = min(1.0, vehicle_count / (MAX_VEHICLES / 2))
        return (speed_factor + count_factor) / 2

    def stop(self):
        """Stop the RSU's communication threads."""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.socket = None

    def __del__(self):
        self.stop() 