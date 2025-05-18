import hashlib
import json
import time
from typing import List, Dict, Any

class Block:
    def __init__(self, index: int, timestamp: float, data: Dict[str, Any], previous_hash: str):
        self.index = index
        self.timestamp = timestamp
        self.data = data
        self.previous_hash = previous_hash
        self.hash = self.calculate_hash()

    def calculate_hash(self) -> str:
        block_string = json.dumps(self.__dict__, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

class Blockchain:
    def __init__(self):
        self.chain: List[Block] = [self.create_genesis_block()]
        self.malicious_vehicles: set = set()

    def create_genesis_block(self) -> Block:
        return Block(0, time.time(), {"message": "Genesis Block"}, "0")

    def get_latest_block(self) -> Block:
        return self.chain[-1]

    def add_block(self, data: Dict[str, Any]) -> Block:
        previous_block = self.get_latest_block()
        new_block = Block(
            previous_block.index + 1,
            time.time(),
            data,
            previous_block.hash
        )
        self.chain.append(new_block)
        return new_block

    def is_chain_valid(self) -> bool:
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i-1]

            if current_block.hash != current_block.calculate_hash():
                return False

            if current_block.previous_hash != previous_block.hash:
                return False

        return True

    def add_malicious_vehicle(self, vehicle_id: str):
        """Add a vehicle to the malicious vehicles list and record it in blockchain."""
        self.malicious_vehicles.add(vehicle_id)
        self.add_block({
            "type": "malicious_vehicle",
            "vehicle_id": vehicle_id,
            "timestamp": time.time()
        })

    def get_malicious_vehicles(self) -> set:
        """Return the set of malicious vehicles."""
        return self.malicious_vehicles

    def record_vehicle_data(self, vehicle_id: str, location: Dict[str, float], 
                          speed: float, direction: float, message: str):
        """Record vehicle data in the blockchain."""
        self.add_block({
            "type": "vehicle_data",
            "vehicle_id": vehicle_id,
            "location": location,
            "speed": speed,
            "direction": direction,
            "message": message,
            "timestamp": time.time()
        })

    def record_rsu_data(self, rsu_id: str, connected_vehicles: List[str], 
                       traffic_data: Dict[str, Any]):
        """Record RSU data in the blockchain."""
        self.add_block({
            "type": "rsu_data",
            "rsu_id": rsu_id,
            "connected_vehicles": connected_vehicles,
            "traffic_data": traffic_data,
            "timestamp": time.time()
        }) 