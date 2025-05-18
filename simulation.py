import time
import random
import socket
import json
import threading
import statistics
import math
import argparse
from typing import Dict, List, Optional
from config import (
    NETWORK_LENGTH, NETWORK_WIDTH, PACKET_SIZE, DATA_RATE,
    VEHICLE_MIN_VELOCITY, VEHICLE_MAX_VELOCITY, RSU_RADIUS,
    MIN_VEHICLE_DELAY, MAX_VEHICLE_DELAY, MIN_VEHICLES, MAX_VEHICLES,
    TCP_CONGESTION_ALGORITHM, ACCIDENT_LOCATION, MAX_V2V_RANGE,
    MAX_V2I_RANGE, RSU_LOCATIONS, TRUST_THRESHOLD, REPUTATION_DECAY,
    SIMULATION_TIMESTEP, SIMULATION_DURATION
)
from blockchain import Blockchain
from vehicle import Vehicle
from rsu import RSU
from algorithms.tmr import TMRRouter
from algorithms.gytar import GyTARRouter
from algorithms.aodv import AODVRouter

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='VANET Simulation System')
    parser.add_argument('--log-type', choices=['vehicle', 'rsu', 'main'],
                       help='Type of logging to display')
    return parser.parse_args()

class VANETSimulation:
    def __init__(self):
        self.blockchain = Blockchain()
        self.vehicles: Dict[str, Vehicle] = {}
        self.rsus: Dict[str, RSU] = {}
        self.running = False
        self.start_time = 0
        self.v2v_delays: List[float] = []
        self.v2i_delays: List[float] = []
        self.malicious_vehicles: set = set()
        
        # Initialize metrics dictionary
        self.metrics = {
            'total_vehicles': 0,
            'malicious_vehicles': 0,
            'v2v_delays': [],
            'v2i_delays': [],
            'avg_v2v_delay': 0,
            'avg_v2i_delay': 0,
            'total_v2v_messages': 0,
            'total_v2i_messages': 0
        }
        
        # Initialize routing algorithms
        self.routers = {
            1: TMRRouter(),
            2: GyTARRouter(),
            3: AODVRouter()
        }
        
        # Setup accident scenario
        self.accident_location = ACCIDENT_LOCATION
        self.accident_reported = False
        
        # Communication metrics
        self.total_messages = 0
        self.successful_deliveries = 0

    def initialize_network(self):
        """Initialize RSUs and vehicles."""
        # Initialize RSUs
        for i, location in enumerate(RSU_LOCATIONS):
            rsu = RSU(f"RSU_{i}", location['x'], location['y'], self.blockchain)
            self.rsus[rsu.id] = rsu
        
        # Generate random number of vehicles
        num_vehicles = random.randint(MIN_VEHICLES, MAX_VEHICLES)
        print(f"\n🚗 Initializing simulation with {num_vehicles} vehicles")
        
        # Initialize vehicles with random positions
        for i in range(num_vehicles):
            x = random.uniform(0, NETWORK_LENGTH)
            y = random.uniform(0, NETWORK_WIDTH)
            vehicle = Vehicle(f"V_{i}", x, y)
            self.vehicles[vehicle.id] = vehicle
        
        # Calculate number of malicious vehicles (3-6% of total vehicles)
        min_malicious = 3  # Minimum number of malicious vehicles
        max_malicious = max(min_malicious + 1, int(0.06 * num_vehicles))  # At most 6% of vehicles, but at least 4
        
        # Ensure max_malicious doesn't exceed total vehicles
        max_malicious = min(max_malicious, num_vehicles - 1)  # Leave at least 1 legitimate vehicle
        
        # Select random number of malicious vehicles
        num_malicious = random.randint(min_malicious, max_malicious)
        self.malicious_ids = random.sample(list(self.vehicles.keys()), num_malicious)
        
        # Store malicious vehicle info but don't display yet
        for vehicle_id in self.malicious_ids:
            self.vehicles[vehicle_id].is_malicious = True
            self.malicious_vehicles.add(vehicle_id)

    def start_simulation(self, algorithm_type: int) -> None:
        """Start the VANET simulation with selected routing algorithm."""
        if algorithm_type not in self.routers:
            raise ValueError("Invalid algorithm type. Choose 1 (TMR), 2 (GyTAR), or 3 (AODV)")
        
        self.running = True
        self.start_time = time.time()
        
        # Now that simulation is starting, show malicious vehicle information
        print(f"\n🚨 Initialized {len(self.malicious_ids)} malicious vehicles "
              f"({(len(self.malicious_ids)/len(self.vehicles))*100:.1f}% of total)")
        
        # Set start time for all vehicles
        for vehicle in self.vehicles.values():
            vehicle.set_simulation_start_time(self.start_time)
        
        # Start simulation threads
        self.update_thread = threading.Thread(target=self._update_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
        
        # Start accident scenario after a delay
        self.accident_thread = threading.Thread(target=self._trigger_accident)
        self.accident_thread.daemon = True
        self.accident_thread.start()

    def stop_simulation(self) -> Dict:
        """Stop the simulation and return results."""
        self.running = False
        # Give threads time to clean up
        time.sleep(1)
        
        end_time = time.time()
        
        # Calculate metrics
        simulation_time = end_time - self.start_time
        avg_v2v_delay = statistics.mean(self.v2v_delays) if self.v2v_delays else 0
        avg_v2i_delay = statistics.mean(self.v2i_delays) if self.v2i_delays else 0
        
        # Clean up
        for vehicle in self.vehicles.values():
            try:
                vehicle.stop()
            except:
                pass
                
        for rsu in self.rsus.values():
            try:
                rsu.stop()
            except:
                pass
        
        return {
            'simulation_time': simulation_time,
            'avg_v2v_delay': avg_v2v_delay,
            'avg_v2i_delay': avg_v2i_delay,
            'total_messages': self.total_messages,
            'successful_deliveries': self.successful_deliveries,
            'delivery_ratio': self.successful_deliveries / self.total_messages if self.total_messages > 0 else 0,
            'malicious_vehicles': list(self.malicious_vehicles)
        }

    def _is_in_range(self, source: Dict[str, float], target: Dict[str, float], is_v2v: bool = True) -> bool:
        """Check if target is within communication range of source."""
        distance = math.sqrt(
            (source['x'] - target['x'])**2 +
            (source['y'] - target['y'])**2
        )
        # Use RSU_RADIUS for V2I and VEHICLE_RANGE for V2V communications
        return distance <= (RSU_RADIUS if not is_v2v else 300)  # 300m for V2V range

    def _check_vehicle_communications(self):
        """Check vehicle communications and update metrics."""
        current_time = time.time()
        
        # Get all malicious vehicles from blockchain
        malicious_vehicles = self.blockchain.get_malicious_vehicles()
        
        # Update metrics for all vehicles
        for vehicle_id, vehicle in self.vehicles.items():
            if vehicle_id in malicious_vehicles:
                continue
                
            # Check V2V communications
            for other_id, other_vehicle in self.vehicles.items():
                if other_id != vehicle_id and other_id not in malicious_vehicles:
                    if self._is_in_range(vehicle.location, other_vehicle.location, is_v2v=True):
                        vehicle.broadcast_beacon()
                        delay = random.uniform(10, 200) / 1000  # 10-200ms in seconds
                        self.v2v_delays.append(delay)
                        self.metrics['total_v2v_messages'] += 1
                        self.total_messages += 1
                        self.successful_deliveries += 1
            
            # Check V2I communications
            for rsu_id, rsu in self.rsus.items():
                if self._is_in_range(vehicle.location, rsu.location, is_v2v=False):
                    vehicle.broadcast_beacon()
                    delay = random.uniform(5, 50) / 1000  # 5-50ms in seconds
                    self.v2i_delays.append(delay)
                    self.metrics['total_v2i_messages'] += 1
                    self.total_messages += 1
                    self.successful_deliveries += 1
        
        # Log malicious vehicle detection
        if malicious_vehicles:
            print("\n🚨 MALICIOUS VEHICLE DETECTION SUMMARY:")
            print(f"Total malicious vehicles: {len(malicious_vehicles)}")
            print(f"Malicious vehicle IDs: {', '.join(malicious_vehicles)}")
            print(f"Remaining legitimate vehicles: {len(self.vehicles) - len(malicious_vehicles)}")

    def _update_loop(self):
        """Main simulation update loop."""
        while self.running:
            # Check if simulation duration has elapsed
            if time.time() - self.start_time >= SIMULATION_DURATION:
                self.running = False
                break
                
            # Update vehicle positions
            for vehicle_id, vehicle in self.vehicles.items():
                vehicle.update_position(SIMULATION_TIMESTEP)
            
            # Check communications
            self._check_vehicle_communications()
            
            # Check for accident scenario
            if not self.accident_reported and time.time() - self.start_time > 10:
                self._trigger_accident()
            
            # Update metrics
            self._update_metrics()
            
            # Sleep for simulation timestep
            time.sleep(SIMULATION_TIMESTEP)

    def _update_metrics(self):
        """Update simulation metrics."""
        current_time = time.time()
        
        # Get malicious vehicles
        malicious_vehicles = self.blockchain.get_malicious_vehicles()
        legitimate_vehicles = [v for v_id, v in self.vehicles.items() if v_id not in malicious_vehicles]
        
        # Update vehicle counts
        self.metrics['total_vehicles'] = len(legitimate_vehicles)
        self.metrics['malicious_vehicles'] = len(malicious_vehicles)
        
        # Calculate running averages for delays
        if self.metrics['total_v2v_messages'] > 0:
            self.metrics['avg_v2v_delay'] = sum(self.v2v_delays) / self.metrics['total_v2v_messages']
        if self.metrics['total_v2i_messages'] > 0:
            self.metrics['avg_v2i_delay'] = sum(self.v2i_delays) / self.metrics['total_v2i_messages']
        
        # Log current state
        print(f"\nSimulation State at {current_time - self.start_time:.1f}s:")
        # print(f"Legitimate vehicles: {len(legitimate_vehicles)}")
        # print(f"Malicious vehicles: {len(malicious_vehicles)}")
        print(f"Total V2V messages: {self.metrics['total_v2v_messages']}")
        print(f"Total V2I messages: {self.metrics['total_v2i_messages']}")
        if self.metrics['avg_v2v_delay']:
            print(f"Average V2V delay: {self.metrics['avg_v2v_delay']*1000:.1f}ms")
        if self.metrics['avg_v2i_delay']:
            print(f"Average V2I delay: {self.metrics['avg_v2i_delay']*1000:.1f}ms")

    def _trigger_accident(self):
        """Simulate accident scenario after delay."""
        if self.running:
            self.accident_reported = True
            print("\n🚨 ACCIDENT SCENARIO TRIGGERED!")
            
            # Find vehicles near accident location
            affected_vehicles = []
            
            for vehicle_id, vehicle in self.vehicles.items():
                distance = math.sqrt(
                    (vehicle.location['x'] - self.accident_location['x'])**2 +
                    (vehicle.location['y'] - self.accident_location['y'])**2
                )
                if distance <= 500:  # Vehicles within 500m
                    affected_vehicles.append(vehicle)
            
            print(f"Found {len(affected_vehicles)} vehicles near accident location")
            
            # Process rerouting decisions
            num_vehicles = len(affected_vehicles)
            staying_on_route = 0
            
            for vehicle in affected_vehicles:
                if vehicle.process_accident_decision(num_vehicles, staying_on_route):
                    staying_on_route += 1
            
            print(f"{staying_on_route} vehicles decided to stay on route")

    def _simulate_network_delays(self):
        """Simulate network conditions and delays."""
        # Limit delay lists to prevent memory issues
        max_delay_history = 1000
        
        if len(self.v2v_delays) > max_delay_history:
            self.v2v_delays = self.v2v_delays[-max_delay_history:]
        
        if len(self.v2i_delays) > max_delay_history:
            self.v2i_delays = self.v2i_delays[-max_delay_history:]

def main():
    """Main simulation control function."""
    args = parse_args()
    
    # If no log type specified, default to main
    if not args.log_type:
        args.log_type = 'main'
    
    # Set up logging based on type
    if args.log_type == 'vehicle':
        print("=== Vehicle Communications Log ===")
        # Only show vehicle messages
        def print_filter(msg):
            return msg.startswith('[') and 'Vehicle' in msg
    elif args.log_type == 'rsu':
        print("=== RSU Communications Log ===")
        # Only show RSU messages
        def print_filter(msg):
            return msg.startswith('[') and 'RSU' in msg
    else:
        print("=== VANET Simulation Main ===")
        # Show only simulation control messages
        def print_filter(msg):
            return not msg.startswith('[')
    
    # Redirect stdout based on log type
    original_print = print
    def filtered_print(*args, **kwargs):
        msg = ' '.join(str(arg) for arg in args)
        if print_filter(msg):
            original_print(*args, **kwargs)
    
    import builtins
    builtins.print = filtered_print
    
    simulation = VANETSimulation()
    
    while True:
        # Initialize new simulation
        simulation.initialize_network()
        
        if args.log_type == 'main':
            # Get algorithm choice
            while True:
                try:
                    algorithm = int(input("Choose routing algorithm (1=TMR, 2=GyTAR, 3=AODV, 4=Auto ): "))
                    if algorithm in [1, 2, 3, 4]:
                        break
                    print("Invalid choice. Please select 1, 2, 3, or 4.")
                except ValueError:
                    print("Invalid input. Please enter a number.")
            
            # 4 Automatic
            if algorithm == 4:
                num_vehicles = len(simulation.vehicles)
                if 11 <= num_vehicles <= 30:
                    algorithm = 3
                elif 30 < num_vehicles <= 60:
                    algorithm = 2
                else:
                    algorithm = 1
            
            # Get start command
            while True:
                start = input("Start simulating? (y/n): ").lower()
                if start in ['y', 'n']:
                    break
                print("Invalid input. Please enter 'y' or 'n'.")
            
            if start == 'y':
                print("\nStarting simulation...\n")

                if algorithm == 1:
                    print("Using TMR algorithm")
                elif algorithm == 2:
                    print("Using GyTAR algorithm")
                elif algorithm == 3:
                    print("Using AODV algorithm")

                simulation.start_simulation(algorithm)
                
                # Wait for simulation to run
                time.sleep(SIMULATION_DURATION)  # Use configured duration
                
                # Stop and get results
                results = simulation.stop_simulation()
                
                # Display results
                print("\nSimulation Results:")
                print(f"Total time: {results['simulation_time']:.2f} seconds")
                print(f"Average V2V delay: {results['avg_v2v_delay']*1000:.2f} ms")
                print(f"Average V2I delay: {results['avg_v2i_delay']*1000:.2f} ms")
                print(f"Message delivery ratio: {results['delivery_ratio']*100:.1f}%")
                print("Malicious vehicles detected:", results['malicious_vehicles'])
                
                # Ask to continue
                while True:
                    again = input("\nRun another simulation? (y/n): ").lower()
                    if again in ['y', 'n']:
                        break
                    print("Invalid input. Please enter 'y' or 'n'.")
                
                if again == 'n':
                    break
            else:
                print("Simulation cancelled.")
                break
        else:
            # For vehicle and RSU logs, just run the simulation with default settings
            simulation.start_simulation(1)  # Use TMR algorithm by default
            time.sleep(SIMULATION_DURATION)  # Use configured duration
            simulation.stop_simulation()
            break
    
    if args.log_type == 'main':
        print("Exiting simulation system.")

if __name__ == "__main__":
    main() 