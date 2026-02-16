import subprocess
import sys
import os
import psutil
from typing import Dict
from shared.logger import logger

class ProcessManager:
    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}

    def start_process(self, name: str, command: list) -> bool:
        """
        Start a process if it's not already running.
        """
        if name in self.processes:
            if self.processes[name].poll() is None:
                logger.warning(f"Process {name} is already running.")
                return True # Already running is "success"
            else:
                 # Cleanup dead process reference
                del self.processes[name]

        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = os.getcwd() # Ensure root is in path
            # Force unbuffered output for Python scripts
            env["PYTHONUNBUFFERED"] = "1" 
            
            logger.info(f"Starting {name} with command: {' '.join(command)}")
            p = subprocess.Popen(
                command, 
                cwd=os.getcwd(),
                env=env,
                # On Windows, CREATE_NEW_CONSOLE might be useful if we want to see separate windows,
                # but for a web UI, we probably want them hidden or just standard child processes.
                # using creationflags=subprocess.CREATE_NEW_CONSOLE would pop up windows.
                # Let's keep them attached or hidden for now.
            )
            self.processes[name] = p
            logger.info(f"✅ Started {name} (PID: {p.pid})")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to start {name}: {e}")
            return False

    def stop_process(self, name: str) -> bool:
        """
        Stop a managed process.
        """
        if name not in self.processes:
            logger.warning(f"Process {name} not found.")
            return False
        
        p = self.processes[name]
        try:
            logger.info(f"Stopping {name} (PID: {p.pid})...")
            parent = psutil.Process(p.pid)
            for child in parent.children(recursive=True):
                child.terminate()
            parent.terminate()
            p.wait(timeout=3)
            del self.processes[name]
            logger.info(f"🛑 Stopped {name}")
            return True
        except psutil.NoSuchProcess:
             del self.processes[name]
             return True
        except Exception as e:
            logger.error(f"Error stopping {name}: {e}")
            try:
                p.kill() # Force kill
                del self.processes[name]
            except:
                pass
            return False

    def get_status(self) -> Dict[str, str]:
        """
        Return status of all managed processes.
        """
        status = {}
        # Check managed processes
        for name, p in list(self.processes.items()):
            if p.poll() is None:
                status[name] = "running"
            else:
                status[name] = "stopped"
                del self.processes[name] # Clean up
        return status

# Thread-safe global instance? 
# FastAPI handles requests primarily in threads, so this simple dict is *okay* for a single worker MVP.
manager = ProcessManager()
