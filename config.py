"""
Configuration parameters for VANET simulation.
"""

# Network Parameters
NETWORK_LENGTH = 3000  # meters
NETWORK_WIDTH = 3000   # meters
PACKET_SIZE = 1024    # Kbps
DATA_RATE = 100       # Mbps
VEHICLE_MIN_VELOCITY = 60  # km/hr
VEHICLE_MAX_VELOCITY = 100 # km/hr
RSU_RADIUS = 1000     # meters
MIN_VEHICLE_DELAY = 10    # ms
MAX_VEHICLE_DELAY = 200   # ms

# Vehicle Count Parameters
MIN_VEHICLES = 11
MAX_VEHICLES = 101

# Accident Scenario
ACCIDENT_LOCATION = {
    'x': 1500,  # T-point location
    'y': 1500
}

# Communication Thresholds
MAX_V2V_RANGE = 300  # meters
MAX_V2I_RANGE = RSU_RADIUS

# RSU Deployment
RSU_LOCATIONS = [
    {'x': 1000, 'y': 1000},
    {'x': 2000, 'y': 1000},
    {'x': 1500, 'y': 2000}
]

# Malicious Vehicle Detection
TRUST_THRESHOLD = 0.5
REPUTATION_DECAY = 0.90

# Simulation Parameters
SIMULATION_TIMESTEP = 0.1  # seconds
SIMULATION_DURATION = 10   # seconds

# TCP Configuration -DEPRECATED
TCP_CONGESTION_ALGORITHM = "veno"