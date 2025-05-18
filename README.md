# VANET Simulation System

A Vehicular Ad-hoc Network (VANET) simulation system implementing multiple routing algorithms and blockchain-based security.

## Features

- Multiple routing algorithms:
  - TMR (Traffic Message Routing)
  - GyTAR (Greedy Traffic Aware Routing)
  - AODV (Ad hoc On-Demand Distance Vector)
- Blockchain-based security for malicious vehicle detection
- Real-time vehicle-to-vehicle (V2V) and vehicle-to-infrastructure (V2I) communication
- Accident scenario simulation with dynamic rerouting
- Network performance metrics and analysis

## Network Specifications

- Network dimensions: 3000m x 3000m
- Packet Size: 1024 Kbps
- Data Rate: 100 Mbps
- Vehicle Velocity: 60-100 km/hr
- RSU Radius: 1000m
- Vehicle Delay: 10-200ms
- Number of Vehicles: 30

## Setup Instructions

1. Create a Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Simulation

1. Start the simulation:
   ```bash
   python simulation.py
   ```

2. Choose a routing algorithm:
   - Enter 1 for TMR
   - Enter 2 for GyTAR
   - Enter 3 for AODV

3. Confirm to start the simulation (y/n)

4. The simulation will run for 30 seconds and display:
   - Total simulation time
   - Average V2V and V2I delays
   - Message delivery ratio
   - List of detected malicious vehicles

5. Choose to run another simulation or exit

## Project Structure

- `simulation.py`: Main simulation controller
- `blockchain.py`: Blockchain implementation for security
- `vehicle.py`: Vehicle node implementation
- `rsu.py`: Road Side Unit implementation
- `config.py`: Network and simulation parameters
- `algorithms/`:
  - `tmr.py`: TMR algorithm implementation
  - `gytar.py`: GyTAR algorithm implementation
  - `aodv.py`: AODV algorithm implementation

## Notes

- The simulation uses TCP Veno as its congestion control algorithm
- RSUs are deployed at strategic locations for optimal coverage
- Malicious vehicles are automatically detected and isolated
- The accident scenario triggers at T-point junction after 10 seconds
- Vehicles make rerouting decisions based on traffic conditions 