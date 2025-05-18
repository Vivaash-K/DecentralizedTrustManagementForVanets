import subprocess
import sys
import os

def run_terminals():
    """Run the three terminals for the VANET simulation."""
    
    # Command to clear the terminal based on OS
    clear_command = 'cls' if os.name == 'nt' else 'clear'
    os.system(clear_command)
    
    print("Starting VANET Simulation System...")
    print("Opening three terminals:")
    print("1. Vehicle Communications")
    print("2. RSU Communications")
    print("3. Main Simulation")
    print("\nPress Ctrl+C in this terminal to stop all processes")
    
    try:
        # Start vehicle communications terminal
        vehicle_cmd = f'python simulation.py --log-type vehicle'
        vehicle_process = subprocess.Popen(['start', 'cmd', '/k', vehicle_cmd], 
                                         shell=True)
        
        # Start RSU communications terminal
        rsu_cmd = f'python simulation.py --log-type rsu'
        rsu_process = subprocess.Popen(['start', 'cmd', '/k', rsu_cmd], 
                                     shell=True)
        
        # Start main simulation terminal
        sim_cmd = f'python simulation.py --log-type main'
        sim_process = subprocess.Popen(['start', 'cmd', '/k', sim_cmd], 
                                     shell=True)
        
        # Wait for user interrupt
        input("Press Enter to stop all processes...")
        
    except KeyboardInterrupt:
        print("\nStopping all processes...")
    finally:
        # Clean up processes
        for process in [vehicle_process, rsu_process, sim_process]:
            try:
                process.terminate()
            except:
                pass
        print("All processes stopped.")

if __name__ == "__main__":
    run_terminals() 