from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from autonomy.utils.data_structures import HighLevelCommand


class CommandParser:
    """Parses natural-language directives into structured commands."""

    DRIVE_TO_PATTERN = re.compile(r"drive\s+to\s+(?P<target>.+)", re.IGNORECASE)
    MOVE_DISTANCE_PATTERN = re.compile(r"drive\s+(?P<distance>\d+(?:\.\d+)?)\s*(m|meters)?\s*(ahead|forward|front)", re.IGNORECASE)
    TURN_PATTERN = re.compile(r"turn\s+(?P<direction>around|left|right)", re.IGNORECASE)

    def parse(self, text: str) -> HighLevelCommand:
        text = text.strip()
        if not text:
            return HighLevelCommand(command_type="idle", raw_text=text)

        distance_match = self.MOVE_DISTANCE_PATTERN.search(text)
        if distance_match:
            distance = float(distance_match.group("distance"))
            return HighLevelCommand(
                command_type="move_distance",
                distance_m=distance,
                raw_text=text,
            )

        turn_match = self.TURN_PATTERN.search(text)
        if turn_match:
            return HighLevelCommand(
                command_type="turn",
                target=turn_match.group("direction").lower(),
                raw_text=text,
            )

        drive_to_match = self.DRIVE_TO_PATTERN.search(text)
        if drive_to_match:
            return HighLevelCommand(
                command_type="navigate_to",
                target=drive_to_match.group("target").strip(),
                raw_text=text,
            )

        if text.lower() in {"stop", "halt"}:
            return HighLevelCommand(command_type="stop", raw_text=text)

        return HighLevelCommand(command_type="free_text", raw_text=text)


class CommandInterface:
    """Watches a text file for operator directives and parses them."""

    def __init__(self, command_file: Optional[Path] = None, initial_command: Optional[str] = None) -> None:
        self._command_file = command_file
        self._parser = CommandParser()
        self._last_mtime: Optional[float] = None
        self._active_command: Optional[HighLevelCommand] = None

        if initial_command:
            self._active_command = self._parser.parse(initial_command)

    @property
    def active_command(self) -> Optional[HighLevelCommand]:
        return self._active_command

    def poll(self) -> Optional[HighLevelCommand]:
        if self._command_file is None:
            return self._active_command

        try:
            stat = self._command_file.stat()
        except FileNotFoundError:
            logging.debug("Command file %s not found", self._command_file)
            return self._active_command

        if self._last_mtime is not None and stat.st_mtime <= self._last_mtime:
            return self._active_command

        self._last_mtime = stat.st_mtime
        text = self._command_file.read_text(encoding="utf-8").strip()
        if not text:
            logging.info("Command file cleared; reverting to idle mode")
            self._active_command = HighLevelCommand(command_type="idle", raw_text="")
            return self._active_command

        logging.info("Loaded new command: %s", text)
        self._active_command = self._parser.parse(text)
        return self._active_command

    def export_state(self, destination: Path) -> None:
        if not destination.parent.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "command_type": self._active_command.command_type if self._active_command else None,
            "target": self._active_command.target if self._active_command else None,
            "distance_m": self._active_command.distance_m if self._active_command else None,
            "raw_text": self._active_command.raw_text if self._active_command else None,
        }
        destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def update_command(self, text: str) -> HighLevelCommand:
        """Parse and activate a new command provided programmatically."""

        parsed = self._parser.parse(text)
        self._active_command = parsed

        if self._command_file is not None:
            try:
                self._command_file.write_text(text, encoding="utf-8")
                self._last_mtime = self._command_file.stat().st_mtime
            except OSError as exc:
                logging.warning("Failed to persist command to %s: %s", self._command_file, exc)

        logging.info("Updated operator command: %s", text)
        return parsed
