"""Smart home simulation plugin."""

import re

from jarvis.core.plugin_base import PluginBase


class SmartHomePlugin(PluginBase):

    name = "smart_home"
    description = "Control smart home devices (lights, thermostat, locks, music)"

    DEVICES = {
        "lights": {"status": "off", "brightness": 100, "color": "white"},
        "thermostat": {"status": "on", "temperature": 72, "mode": "auto"},
        "front_door": {"status": "locked"},
        "back_door": {"status": "locked"},
        "garage": {"status": "closed"},
        "music": {"status": "off", "volume": 50, "track": "None"},
        "security": {"status": "armed", "cameras": "active"},
    }

    TRIGGERS = [
        r"\b(light|lamp|brightness|dim|dark)\b",
        r"\b(thermostat|temperature|heat|cool|warm|cold|ac|hvac)\b",
        r"\b(lock|unlock|door|garage|gate)\b",
        r"\b(music|play|pause|stop|volume|song|track|speaker)\b",
        r"\b(security|alarm|camera|arm|disarm)\b",
        r"\b(turn on|turn off|switch on|switch off|shut)\b",
        r"\b(home|house)\b.*\b(status|report)\b",
    ]

    def can_handle(self, text):
        return any(re.search(t, text, re.IGNORECASE) for t in self.TRIGGERS)

    def handle(self, text):
        lower = text.lower()

        if re.search(r"\b(home|house)\b.*\b(status|report)\b", lower):
            return self._home_status()

        if re.search(r"\blight\b|lamp|brightness|dim", lower):
            return self._handle_lights(lower)
        elif re.search(r"\bthermostat|temperature|heat|cool|warm|cold", lower):
            return self._handle_thermostat(lower)
        elif re.search(r"\block|unlock|door|garage", lower):
            return self._handle_locks(lower)
        elif re.search(r"\bmusic|play|pause|stop|volume|song|speaker", lower):
            return self._handle_music(lower)
        elif re.search(r"\bsecurity|alarm|camera|arm|disarm", lower):
            return self._handle_security(lower)
        elif re.search(r"\bturn\s+(on|off)|switch\s+(on|off)", lower):
            return self._handle_toggle(lower)

        return self._home_status()

    def _handle_lights(self, text):
        lights = self.DEVICES["lights"]
        if "off" in text or "dark" in text:
            lights["status"] = "off"
            return "Lights turned off, sir."
        elif "on" in text:
            lights["status"] = "on"
            return f"Lights turned on at {lights['brightness']}% brightness."
        elif "dim" in text:
            lights["status"] = "on"
            lights["brightness"] = 30
            return "Lights dimmed to 30%, sir."
        elif "bright" in text:
            lights["status"] = "on"
            lights["brightness"] = 100
            return "Lights set to full brightness, sir."
        else:
            return f"Lights are currently {lights['status']} at {lights['brightness']}% brightness."

    def _handle_thermostat(self, text):
        thermo = self.DEVICES["thermostat"]
        temp_match = re.search(r"(\d+)\s*(degrees|f|c)?", text)
        if temp_match:
            temp = int(temp_match.group(1))
            thermo["temperature"] = temp
            return f"Thermostat set to {temp} degrees, sir."
        elif "warm" in text or "heat" in text:
            thermo["temperature"] += 3
            return f"Raising temperature to {thermo['temperature']} degrees, sir."
        elif "cool" in text or "cold" in text:
            thermo["temperature"] -= 3
            return f"Lowering temperature to {thermo['temperature']} degrees, sir."
        else:
            return f"Thermostat is set to {thermo['temperature']} degrees in {thermo['mode']} mode."

    def _handle_locks(self, text):
        if "garage" in text:
            device = self.DEVICES["garage"]
            if "open" in text:
                device["status"] = "open"
                return "Garage door opened, sir."
            elif "close" in text:
                device["status"] = "closed"
                return "Garage door closed, sir."
            return f"Garage is currently {device['status']}."

        door = "front_door" if "front" in text else "back_door"
        device = self.DEVICES[door]
        label = door.replace("_", " ")
        if "unlock" in text:
            device["status"] = "unlocked"
            return f"{label.title()} unlocked, sir."
        elif "lock" in text:
            device["status"] = "locked"
            return f"{label.title()} locked, sir."
        return f"{label.title()} is currently {device['status']}."

    def _handle_music(self, text):
        music = self.DEVICES["music"]
        if "stop" in text or "pause" in text:
            music["status"] = "paused"
            return "Music paused, sir."
        elif "play" in text:
            music["status"] = "playing"
            track_match = re.search(r"play\s+(.+)", text)
            if track_match:
                track = track_match.group(1).strip()
                music["track"] = track
                return f"Now playing: {track}"
            return "Music resumed, sir."
        elif "volume" in text:
            vol_match = re.search(r"(\d+)", text)
            if vol_match:
                music["volume"] = int(vol_match.group(1))
            elif "up" in text:
                music["volume"] = min(100, music["volume"] + 10)
            elif "down" in text:
                music["volume"] = max(0, music["volume"] - 10)
            return f"Volume set to {music['volume']}%, sir."
        return f"Music is {music['status']}. Volume: {music['volume']}%."

    def _handle_security(self, text):
        sec = self.DEVICES["security"]
        if "disarm" in text or "off" in text:
            sec["status"] = "disarmed"
            return "Security system disarmed, sir."
        elif "arm" in text or "on" in text:
            sec["status"] = "armed"
            return "Security system armed. All cameras active, sir."
        return f"Security: {sec['status']}. Cameras: {sec['cameras']}."

    def _handle_toggle(self, text):
        on = "on" in text
        for device_name in self.DEVICES:
            if device_name.replace("_", " ") in text or device_name in text:
                self.DEVICES[device_name]["status"] = "on" if on else "off"
                return f"{device_name.replace('_', ' ').title()} turned {'on' if on else 'off'}, sir."
        return "Which device would you like me to toggle, sir?"

    def _home_status(self):
        lines = ["Home Status Report:\n"]
        for name, state in self.DEVICES.items():
            label = name.replace("_", " ").title()
            status = state.get("status", "unknown")
            lines.append(f"  {label:15s} : {status}")
        return "\n".join(lines)
