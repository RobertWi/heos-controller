import json
import os
from typing import List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class CommandHistory:
    def __init__(self, history_file: str = "command_history.json"):
        self.history_file = history_file
        self.history: List[Dict[str, Any]] = []
        self.load_history()

    def load_history(self) -> None:
        """Load command history from file."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    self.history = json.load(f)
                logger.info(f"Loaded {len(self.history)} commands from history")
        except Exception as e:
            logger.error(f"Error loading history: {e}")
            self.history = []

    def save_history(self) -> None:
        """Save command history to file."""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=2)
            logger.debug("History saved successfully")
        except Exception as e:
            logger.error(f"Error saving history: {e}")

    def add_command(self, command: str, device: Dict[str, Any], response: Any = None) -> None:
        """Add a command to history."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'command': command,
            'device': {
                'name': device.get('name', 'Unknown'),
                'ip': device.get('ip', 'Unknown'),
                'model': device.get('model', 'Unknown')
            },
            'response': response
        }
        self.history.append(entry)
        self.save_history()
        logger.debug(f"Added command to history: {command}")

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get command history, most recent first."""
        return sorted(
            self.history, 
            key=lambda x: x['timestamp'], 
            reverse=True
        )[:limit]

    def clear_history(self) -> None:
        """Clear command history."""
        self.history = []
        self.save_history()
        logger.info("Command history cleared")
