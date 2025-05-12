import socket
import json
from typing import Dict, Optional, List, Any, Tuple
import time
import logging

logger = logging.getLogger(__name__)

# --- Configuration for Hyperion ---
HYPERION_DEFAULT_PORT = 19444
HYPERION_DEFAULT_PRIORITY = 50  # Docs recommend 50 for apps
HYPERION_COMPONENT_LEDDEVICE = "LEDDEVICE"
HYPERION_ORIGIN_NAME = "LEDController"  # Min 4, Max 20 chars for origin

WLED_TO_HYPERION_EFFECT_MAP: Dict[int, str] = {
    # 0: "Solid" - Intentionally left out, recommend using controller.set_color()
    #            or map to a generic mood blob if a default "on" effect is desired
    # 0: "Warm mood blobs", # Example if you want set_effect(0) to do *something*
    2: "Breath",
    5: "Random",
    7: "Random", # Dynamic is similar to Random
    8: "Rainbow mood", # Colorloop
    9: "Rainbow swirl", # Rainbow
    10: "Knight rider", # Scan
    11: "Knight rider", # Scan Dual (Hyperion's Knight Rider might be configurable or just look similar)
    12: "Breath", # Fade
    # 13: "Cinema dim lights", # Theater (thematic, not necessarily visual match)
    15: "Waves with Color", # Running (sine waves)
    17: "Sparks", # Twinkle
    20: "Sparks", # Sparkle
    # 23: "Strobe white", # Strobe (color needs to be a param of Strobe white, or use specific like Strobe red)
    28: "Snake", # Chase
    # 30: "Rainbow swirl", # Chase Rainbow (if snake can't take rainbow palette easily)
    38: "Cold mood blobs", # Aurora (approximation)
    40: "Knight rider", # Scanner
    42: "Sparks",       # Fireworks (approximation for visual bursts)
    43: "Sparks",       # Rain (approximation for falling/appearing sparks)
    45: "Fire",         # Fire Flicker
    47: "Knight rider", # Loading (as used in previous examples, a moving bar)
    49: "X-Mas",        # Fairy (thematic)
    51: "X-Mas",        # Fairytwinkle
    57: "Strobe white", # Lightning (if very brief) or "Sparks"
    63: "Rainbow swirl",# Pride 2015
    66: "Fire",         # Fire 2012
    67: "Waves with Color", # Colorwaves
    74: "Sparks",       # Colortwinkles
    75: "Sea waves",    # Lake
    76: "Trails",       # Meteor
    77: "Trails",       # Meteor Smooth
    # 79: "Sea waves",    # Ripple (if Hyperion's Sea Waves has ripple)
    80: "X-Mas",        # Twinklefox (thematic)
    88: "Candle",       # Candle
    89: "Sparks",       # Fireworks Starburst
    92: "Knight rider", # Sinelon (Knight rider is a common term for this visual)
    97: "Plasma",       # Plasma
    100: "Breath",      # Heartbeat (if speed can be matched)
    101: "Sea waves",   # Pacifica
    102: "Candle",      # Candle Multi
    105: "Waves with Color", # Phased
    108: "Waves with Color", # Sine
    # Many 2D (▦) and Audio (♫, ♪) effects are omitted due to difficulty in direct mapping
    # to simple Hyperion effects via this API.
    121: "Full color mood blobs", # Blobs (generic)
    131: "Matrix",      # Matripix (if Hyperion's Matrix is non-audio)
    153: "Matrix",      # Matrix (WLED) -> Matrix (Hyperion)
    154: "Plasma",      # Metaballs
    162: "Waves with Color", # Pulser
    166: "Warm mood blobs", # Sun Radiation (approximation)
    175: "Double swirl",# Swirl (non-audio approximation)
    179: "Rainbow swirl", # Flow Stripe
    180: "Plasma",      # Hiphotic
    183: "Atomic swirl",# Black Hole (approximation)
    184: "Waves with Color", # Wavesins
}

WLED_TO_HYPERION_PRESET_MAP: Dict[int, Dict[str, Any]] = {
    1: {
        "type": "effect",
        "name": "Preset01",
        "args": {
        }
    },  
    # IMPORTANT NOTE: I cannot find a way to do a single color with Hyperion presets.  If you want to change preset 1 to be a single color, you can modify the foregoing code to read 1: {"type": "color", "rgb": [76, 245, 245]},
    2: {
        "type": "effect",
        "name": "Preset02",
        "args": {
        }
    },
}

class LEDController:
    def __init__(self, ip_address: Optional[str] = None, port: int = HYPERION_DEFAULT_PORT):
        self.ip_address = ip_address
        self.port = port
        self.priority = HYPERION_DEFAULT_PRIORITY
        self.auth_token: Optional[str] = None
        self.origin = HYPERION_ORIGIN_NAME  # Origin for commands sent to Hyperion

    def set_ip(self, ip_address: str, port: Optional[int] = None) -> None:
        """Update the Hyperion IP address and optionally the port."""
        self.ip_address = ip_address
        if port is not None:
            self.port = port

    def set_auth_token(self, token: str) -> None:
        """Set authentication token if Hyperion requires it."""
        self.auth_token = token

    def _send_hyperion_command(self, command_obj: Dict) -> Optional[Dict]:
        """Sends a command to Hyperion via TCP socket and returns the JSON response."""
        if not self.ip_address:
            # This will be caught by the calling method (_send_command)
            raise ValueError("No Hyperion IP configured")

        # Add authentication token if available
        if self.auth_token:
            command_obj["token"] = self.auth_token
        
        # Add tan for synchronous response if not already present (good practice)
        if "tan" not in command_obj:
            # Generate a somewhat unique tan; simple epoch ms % range
            command_obj["tan"] = int(time.time() * 1000) % 100000

        full_request = json.dumps(command_obj) + "\n"
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3)  # Connection and read timeout
                s.connect((self.ip_address, self.port))
                s.sendall(full_request.encode('utf-8'))

                response_data = ""
                buffer = ""
                # Hyperion sends line-separated JSON. Read until a full JSON object is likely received.
                while True:
                    chunk = s.recv(4096).decode('utf-8', errors='ignore')
                    if not chunk:  # Connection closed by peer
                        break
                    buffer += chunk
                    if "\n" in buffer:  # Assuming one JSON response per command, ending with newline
                        response_data = buffer.split("\n", 1)[0]
                        break # Got a full line / complete JSON message
                
                if not response_data.strip():
                    logger.error(f"No response data received from Hyperion for command: {command_obj.get('command')}")
                    # This case indicates a problem, as Hyperion should always send a JSON response.
                    raise json.JSONDecodeError("No response data from Hyperion", "", 0)

                response_json = json.loads(response_data.strip())
                
                # Log if Hyperion command itself was not successful
                if not response_json.get("success", False):
                    error_info = response_json.get("error", "Unknown error from Hyperion")
                    logger.error(
                        f"Hyperion command failed: {command_obj.get('command')} - "
                        f"Error: '{error_info}'. Request: {json.dumps(command_obj)}"
                    )
                    # The calling function (_send_command) will use this to format its return dict
                return response_json

        except socket.timeout:
            logger.error(f"Timeout connecting/reading from Hyperion at {self.ip_address}:{self.port}")
            raise ConnectionError(f"Timeout communicating with Hyperion at {self.ip_address}:{self.port}")
        except ConnectionRefusedError:
            logger.error(f"Connection refused by Hyperion at {self.ip_address}:{self.port}")
            raise ConnectionRefusedError(f"Connection refused by Hyperion at {self.ip_address}:{self.port}")
        except OSError as e:  # Other socket errors (e.g., host not found, network unreachable)
            logger.error(f"Socket OS error with Hyperion: {e}")
            raise ConnectionError(f"Socket OS error with Hyperion: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing Hyperion response: {e}. Received data: '{response_data[:200]}'")
            raise # Re-raise to be caught by _send_command

    def _get_hyperion_serverinfo(self) -> Optional[Dict]:
        """Fetches the 'serverinfo' from Hyperion."""
        try:
            response = self._send_hyperion_command({"command": "serverinfo"})
            return response.get("info") if response and response.get("success") else None
        except Exception as e: # Catch exceptions from _send_hyperion_command
            logger.warning(f"Could not get Hyperion serverinfo: {e}")
            return None

    def _send_command(self, state_params: Dict = None) -> Dict:
        """
        Translates WLED-style state_params into Hyperion commands and
        returns a status dictionary in the WLED-like format.
        """
        try:
            if not self.ip_address:
                raise ValueError("No Hyperion IP configured")

            # --- Pre-command: Auto Power-On Logic (like WLED) ---
            # Get current Hyperion LEDDEVICE state before sending new commands
            server_info_before = self._get_hyperion_serverinfo()
            is_hyperion_leddevice_on_before = False
            if server_info_before:
                for comp in server_info_before.get("components", []):
                    if comp.get("name") == HYPERION_COMPONENT_LEDDEVICE:
                        is_hyperion_leddevice_on_before = comp.get("enabled", False)
                        break
            
            is_power_control_command = state_params is not None and "on" in state_params
            is_visual_effect_command = state_params and any(k in state_params for k in ["bri", "seg", "ps"])

            # If LEDDEVICE is off, and we are trying to set a visual (not just power), turn it on
            if not is_hyperion_leddevice_on_before and state_params and \
               is_visual_effect_command and not is_power_control_command:
                logger.debug("Hyperion LEDDEVICE is off, attempting to turn on first.")
                self._send_hyperion_command({
                    "command": "componentstate",
                    "componentstate": {"component": HYPERION_COMPONENT_LEDDEVICE, "state": True}
                })
                time.sleep(0.1) # Give Hyperion a moment to process the power-on

            # --- Process state_params (WLED style) into Hyperion commands ---
            if state_params:
                # Power ("on")
                if "on" in state_params:
                    power_val = state_params["on"]
                    target_leddevice_state = bool(power_val)
                    if isinstance(power_val, str) and power_val.lower() == "t": # Toggle
                        # Use the state fetched before, or fetch again if it was unavailable
                        current_led_state_for_toggle = is_hyperion_leddevice_on_before
                        if server_info_before is None: # If initial fetch failed
                             current_info_for_toggle = self._get_hyperion_serverinfo()
                             if current_info_for_toggle:
                                 for comp in current_info_for_toggle.get("components", []):
                                     if comp.get("name") == HYPERION_COMPONENT_LEDDEVICE:
                                         current_led_state_for_toggle = comp.get("enabled", False)
                                         break
                        target_leddevice_state = not current_led_state_for_toggle
                    
                    self._send_hyperion_command({
                        "command": "componentstate",
                        "componentstate": {"component": HYPERION_COMPONENT_LEDDEVICE, "state": target_leddevice_state}
                    })

                # Brightness ("bri") - WLED 0-255 -> Hyperion brightness 0-100
                if "bri" in state_params:
                    wled_brightness_param = int(state_params["bri"])
                    hyperion_brightness_target = max(0, min(100, round((wled_brightness_param / 255.0) * 100)))
                    self._send_hyperion_command({
                        "command": "adjustment",
                        "adjustment": {"brightness": hyperion_brightness_target} # Value is an object
                    })
                
                # Segments ("seg") - For color or effect (applies globally in Hyperion via this API)
                if "seg" in state_params and isinstance(state_params["seg"], list) and state_params["seg"]:
                    # Assume WLED's first segment definition applies globally to Hyperion
                    segment_data = state_params["seg"][0] 

                    # Effect ("fx")
                    if "fx" in segment_data:
                        wled_effect_idx = segment_data["fx"]
                        hyperion_effect_name = WLED_TO_HYPERION_EFFECT_MAP.get(wled_effect_idx)
                        if hyperion_effect_name:
                            hyperion_effect_args = {}
                            # WLED speed (sx) and intensity (ix) are 0-255.
                            # Hyperion effect args are effect-specific. Common ones might be "speed", "intensity".
                            # This mapping is very approximate and may need per-effect tuning.
                            if "sx" in segment_data: # WLED Speed
                                # Example scaling: WLED 0-255 -> Hyperion 0.1-2.0 (adjust as needed)
                                hyperion_effect_args["speed"] = max(0.1, segment_data["sx"] / 128.0) 
                            if "ix" in segment_data: # WLED Intensity
                                # Example scaling: WLED 0-255 -> Hyperion 0.1-2.0 (adjust as needed)
                                hyperion_effect_args["intensity"] = max(0.1, segment_data["ix"] / 128.0)
                            
                            # Colors ("col") for the effect
                            # WLED: "col": [[r,g,b,w?], [r2,g2,b2,w2?], ...]
                            # Hyperion effects might take a "colors" arg as [[r,g,b],[r,g,b]] or "color" as [r,g,b]
                            if "col" in segment_data and segment_data["col"]:
                                effect_colors_rgb_only = [c[:3] for c in segment_data["col"]] # Take RGB, ignore W
                                if effect_colors_rgb_only:
                                     # Hyperion effects define their own arg names. "colors" and "color" are common.
                                    if len(effect_colors_rgb_only) == 1:
                                        hyperion_effect_args["color"] = effect_colors_rgb_only[0]
                                    hyperion_effect_args["colors"] = effect_colors_rgb_only # Pass array of colors
                            
                            # Palette ("pal") - WLED palette index
                            # Hyperion effects typically don't take a generic palette index this way.
                            # This will likely be ignored unless a specific Hyperion effect uses an arg named "palette".
                            if "pal" in segment_data:
                                hyperion_effect_args["palette"] = segment_data["pal"] # Highly speculative

                            self._send_hyperion_command({
                                "command": "effect",
                                "effect": {"name": hyperion_effect_name, "args": hyperion_effect_args},
                                "priority": self.priority,
                                "origin": self.origin # Name of the controlling application
                            })
                        else:
                            logger.warning(f"No Hyperion effect mapping for WLED effect index: {wled_effect_idx}")
                    
                    # Solid Color (if no "fx" in segment, but "col" is present)
                    elif "col" in segment_data and segment_data["col"]:
                        # Use the first color defined in WLED segment, RGB components only
                        rgb_color_to_set = segment_data["col"][0][:3] 
                        self._send_hyperion_command({
                            "command": "color",
                            "color": rgb_color_to_set,
                            "priority": self.priority,
                            "origin": self.origin
                        })
                
                # Preset ("ps")
                if "ps" in state_params:
                    wled_preset_id = state_params["ps"]
                    hyperion_preset_action = WLED_TO_HYPERION_PRESET_MAP.get(wled_preset_id)
                    if hyperion_preset_action:
                        # Construct command based on preset_action type
                        cmd_details_for_preset = {
                            "priority": self.priority,
                            "origin": f"{self.origin}_P{wled_preset_id}"[:20] # Ensure origin length compliance
                        }
                        if hyperion_preset_action["type"] == "effect":
                            cmd_details_for_preset["command"] = "effect"
                            cmd_details_for_preset["effect"] = {
                                "name": hyperion_preset_action["name"],
                                "args": hyperion_preset_action.get("args", {})
                            }
                        elif hyperion_preset_action["type"] == "color":
                            cmd_details_for_preset["command"] = "color"
                            cmd_details_for_preset["color"] = hyperion_preset_action["rgb"]
                        
                        self._send_hyperion_command(cmd_details_for_preset)
                    else:
                        logger.warning(f"No Hyperion preset mapping for WLED preset ID: {wled_preset_id}")
                
                # WLED transition - Hyperion has global smoothing, not per-command transitions easily via this API.
                if "transition" in state_params:
                    logger.debug("Hyperion adapter: WLED 'transition' parameter is ignored for commands.")

            # --- Fetch final state from Hyperion to construct WLED-like response ---
            final_hyperion_info = self._get_hyperion_serverinfo()
            if final_hyperion_info is None:
                # If we can't get serverinfo after commands, assume a connection issue persisted or occurred.
                raise ConnectionError("Failed to get Hyperion serverinfo after command execution.")

            # Determine final 'is_on' state from LEDDEVICE component
            is_on_final = False
            for comp in final_hyperion_info.get("components", []):
                if comp.get("name") == HYPERION_COMPONENT_LEDDEVICE:
                    is_on_final = comp.get("enabled", False)
                    break
            
            # Determine final brightness (Hyperion 0-100, scale to WLED 0-255)
            hyperion_brightness_final_val = 100 # Default if not found
            adjustments_list = final_hyperion_info.get("adjustment", []) # serverinfo.adjustment is a list
            if adjustments_list and isinstance(adjustments_list, list) and adjustments_list:
                 # Find the brightness adjustment. Usually in the first/default adjustment object.
                for adj_item in adjustments_list:
                    if "brightness" in adj_item:
                        hyperion_brightness_final_val = adj_item.get("brightness", 100)
                        break # Found brightness, use it

            wled_brightness_final = round((hyperion_brightness_final_val / 100.0) * 255)

            # Determine active WLED-mapped preset ID (complex part)
            active_wled_preset_id = -1
            hyperion_priorities = final_hyperion_info.get("priorities", [])
            # Find the source that is currently visible on the LEDs
            visible_priority_source = next((p for p in hyperion_priorities if p.get("visible")), None)

            if visible_priority_source:
                component_id = visible_priority_source.get("componentId")
                owner_name = visible_priority_source.get("owner") # For EFFECT, this is the effect name
                active_color_rgb = visible_priority_source.get("value", {}).get("RGB") # For COLOR

                for wled_pid, preset_action_def in WLED_TO_HYPERION_PRESET_MAP.items():
                    if preset_action_def["type"] == "effect" and component_id == "EFFECT" and \
                       preset_action_def["name"] == owner_name:
                        # Simplistic match by name; args could also be compared for more accuracy
                        active_wled_preset_id = wled_pid
                        break
                    elif preset_action_def["type"] == "color" and component_id == "COLOR" and \
                         active_color_rgb and \
                         all(a == b for a,b in zip(preset_action_def["rgb"], active_color_rgb)): # Compare RGB lists
                        active_wled_preset_id = wled_pid
                        break
            
            return {
                "connected": True,
                "is_on": is_on_final,
                "preset_id": active_wled_preset_id,
                "playlist_id": -1, # Hyperion doesn't have a direct WLED-style playlist concept via this API
                "brightness": wled_brightness_final,
                "message": "Hyperion is ON" if is_on_final else "Hyperion is OFF"
            }

        except ValueError as e: # e.g. IP not configured
            return {"connected": False, "message": str(e)}
        # Catch more specific connection errors first
        except (ConnectionRefusedError, ConnectionError, socket.gaierror, socket.timeout) as e: # gaierror for DNS issues
             return {"connected": False, "message": f"Cannot connect to Hyperion: {str(e)}"}
        except json.JSONDecodeError as e: # From _send_hyperion_command if parsing fails
            return {"connected": False, "message": f"Error parsing Hyperion response: {str(e)}"}
        except Exception as e: # Catch-all for other unexpected issues during the process
            logger.exception("Unexpected error in _send_command for Hyperion adapter")
            return {"connected": False, "message": f"Unexpected Hyperion adapter error: {str(e)}"}

    # --- Public methods mimicking WLEDController interface ---
    def check_wled_status(self) -> Dict:
        """Check Hyperion connection status and its current state (brightness, power)."""
        return self._send_command() # No params, just gets status translated to WLED format

    def set_brightness(self, value: int) -> Dict:
        """Set Hyperion global brightness (WLED scale 0-255)."""
        if not 0 <= value <= 255:
            return {"connected": False, "message": "Brightness must be between 0 and 255"}
        return self._send_command({"bri": value})

    def set_power(self, state: int) -> Dict:
        """Set Hyperion LEDDEVICE power state (0=Off, 1=On, 2=Toggle)."""
        if state not in [0, 1, 2]:
            return {"connected": False, "message": "Power state must be 0 (Off), 1 (On), or 2 (Toggle)"}
        if state == 2: # Toggle
            return self._send_command({"on": "t"})
        return self._send_command({"on": bool(state)}) # 0 is False, 1 is True

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color string (e.g., '#FF0000') to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6:
            raise ValueError("Hex color must be 6 characters long (without #)")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def set_color(self, r: int = None, g: int = None, b: int = None, w: int = None, hex: str = None) -> Dict:
        """Set Hyperion to a solid color using RGB values or hex code."""
        rgb_to_set: List[int] = [0,0,0] # Default to black if no color specified
        if hex is not None:
            try:
                r_hex, g_hex, b_hex = self._hex_to_rgb(hex)
                rgb_to_set = [r_hex, g_hex, b_hex]
            except ValueError as e:
                return {"connected": False, "message": str(e)}
        elif any(val is not None for val in [r, g, b]): # Only set if r,g or b is provided
            rgb_to_set = [r or 0, g or 0, b or 0]

        # Hyperion's basic color command is RGB. 'w' (white channel) from WLED is ignored here.
        if w is not None:
            logger.warning("Hyperion adapter: 'w' (white channel) in set_color is currently ignored for basic color command.")
        
        # Translate to WLED-style state_params for _send_command
        return self._send_command({"seg": [{"col": [rgb_to_set]}]})

    def set_effect(self, effect_index: int, speed: int = None, intensity: int = None, 
                   brightness: int = None, palette: int = None,
                   # Primary color
                   r: int = None, g: int = None, b: int = None, w: int = None, hex: str = None,
                   # Secondary color
                   r2: int = None, g2: int = None, b2: int = None, w2: int = None, hex2: str = None,
                   # Transition (WLED specific, ignored by Hyperion in this context)
                   transition: int = 0) -> Dict:
        """Set Hyperion effect (mapped from WLED effect_index) with optional parameters."""
        try:
            wled_effect_idx_int = int(effect_index)
        except (ValueError, TypeError):
            return {"connected": False, "message": "Effect index must be a valid integer"}

        # WLED effect indices (e.g. 0-101). Hyperion effect names are from WLED_TO_HYPERION_EFFECT_MAP.
        # Validation for WLED's 0-101 range is implicitly handled by the map lookup.
        
        # Construct the 'seg' part of WLED-style state_params
        seg_payload_for_wled_style: Dict[str, Any] = {"fx": wled_effect_idx_int}
        colors_for_effect_param = [] # List of color arrays [[R,G,B], [R2,G2,B2]]

        # Primary color processing
        primary_color_components_rgb: Optional[List[int]] = None
        if hex is not None:
            try:
                r_p, g_p, b_p = self._hex_to_rgb(hex)
                primary_color_components_rgb = [r_p, g_p, b_p]
            except ValueError as e:
                return {"connected": False, "message": f"Primary color hex error: {str(e)}"}
        elif any(val is not None for val in [r, g, b]): # If RGB values are given
            primary_color_components_rgb = [r or 0, g or 0, b or 0]
        
        if primary_color_components_rgb: # Only add if color was actually specified
            # WLED effects can use 'w', Hyperion effects typically don't use it directly in 'color'/'colors' arg
            if w is not None: 
                if not 0 <= w <= 255: return {"connected": False, "message": "Primary white value must be between 0 and 255"}
                # primary_color_components_rgb.append(w) # WLED would include W; Hyperion usually expects RGB
                logger.debug("Primary 'w' channel for effect color ignored for Hyperion effect color arguments.")
            colors_for_effect_param.append(primary_color_components_rgb)

        # Secondary color processing
        secondary_color_components_rgb: Optional[List[int]] = None
        if hex2 is not None:
            try:
                r_s, g_s, b_s = self._hex_to_rgb(hex2)
                secondary_color_components_rgb = [r_s, g_s, b_s]
            except ValueError as e:
                return {"connected": False, "message": f"Secondary color hex error: {str(e)}"}
        elif any(val is not None for val in [r2, g2, b2]): # If RGB values are given
            secondary_color_components_rgb = [r2 or 0, g2 or 0, b2 or 0]

        if secondary_color_components_rgb: # Only add if color was actually specified
            if w2 is not None:
                if not 0 <= w2 <= 255: return {"connected": False, "message": "Secondary white value must be between 0 and 255"}
                logger.debug("Secondary 'w' channel for effect color ignored for Hyperion effect color arguments.")
            colors_for_effect_param.append(secondary_color_components_rgb)
        
        if colors_for_effect_param: # If any colors were specified
            seg_payload_for_wled_style["col"] = colors_for_effect_param
        
        # Add other WLED-style effect parameters for translation by _send_command
        if speed is not None:
            if not 0 <= speed <= 255: return {"connected": False, "message": "Speed must be between 0 and 255"}
            seg_payload_for_wled_style["sx"] = speed
        
        if intensity is not None:
            if not 0 <= intensity <= 255: return {"connected": False, "message": "Intensity must be between 0 and 255"}
            seg_payload_for_wled_style["ix"] = intensity
        
        if palette is not None: # WLED palette index
            if not 0 <= palette <= 46: # Original WLED validation for its palettes
                 return {"connected": False, "message": "Palette index must be between 0 and 46"}
            seg_payload_for_wled_style["pal"] = palette

        # Combine into final WLED-style state_params dictionary
        final_state_params_for_wled_style: Dict[str, Any] = {"seg": [seg_payload_for_wled_style]}
        
        if brightness is not None: # This is overall brightness for Hyperion
            if not 0 <= brightness <= 255: return {"connected": False, "message": "Brightness must be between 0 and 255"}
            final_state_params_for_wled_style["bri"] = brightness
        
        # WLED transition parameter. _send_command will note that it's ignored for Hyperion.
        if transition != 0: # Default is 0 for WLED (instant change)
             final_state_params_for_wled_style["transition"] = transition

        return self._send_command(final_state_params_for_wled_style)

    def set_preset(self, preset_id: int) -> Dict:
        """Set a Hyperion state corresponding to a WLED preset ID (via mapping)."""
        try:
            pid = int(preset_id)
        except ValueError:
             return {"connected": False, "message": "Preset ID must be an integer"}
        
        response = self._send_command({"ps": pid})
        # logger.debug(f"Set Hyperion preset (mapped from WLED ID {pid}): {response}") # Logging happens in _send_command
        return response


# --- Helper Functions (Unchanged, they use the LEDController interface) ---

def effect_loading(led_controller: LEDController):
    """Activates a 'loading' effect using the LEDController."""
    # WLED effect 47, speed 150, intensity 150
    # Orange (#ffa000) and Black (#000000)
    # Palette 0
    # This now depends on WLED_TO_HYPERION_EFFECT_MAP[47] and how that Hyperion
    # effect handles 'speed', 'intensity', 'color'/'colors', and 'palette' args.
    res = led_controller.set_effect(
        effect_index=47,
        hex='#ffa000',
        hex2='#000000',
        palette=0,
        speed=150,
        intensity=150
    )
    return res.get('is_on', False) # Check if Hyperion is reported as ON

def effect_idle(led_controller: LEDController):
    """Sets Hyperion to an 'idle' state via a mapped WLED preset."""
    # This depends on WLED_TO_HYPERION_PRESET_MAP[1]
    led_controller.set_preset(1)


def effect_connected(led_controller: LEDController):
    """Plays a short 'connected' animation using the LEDController."""
    # Original WLED Effect 0 (Solid), Green (#08ff00), Brightness 100
    # This now depends on WLED_TO_HYPERION_EFFECT_MAP[0] or how set_color is handled.
    # If effect 0 is "Solid" in Hyperion, it will try to set color [8,255,0] and global brightness.
    res = led_controller.set_effect(effect_index=0, hex='#08ff00', brightness=100)
    time.sleep(1)

    # Original WLED: Effect 0 (Solid), Brightness 0 (effectively off for that effect color)
    # For Hyperion adapter: sets effect mapped from WLED ID 0 AND sets global Hyperion brightness to 0.
    led_controller.set_effect(effect_index=0, brightness=0) # Sets mapped effect and global brightness
    time.sleep(0.5)

    res = led_controller.set_effect(effect_index=0, hex='#08ff00', brightness=100)
    time.sleep(1)

    effect_idle(led_controller) # Switch to idle state
    return res.get('is_on', False)

def effect_playing(led_controller: LEDController):
    """Sets Hyperion to a 'playing' state via a mapped WLED preset."""
    # This depends on WLED_TO_HYPERION_PRESET_MAP[2]
    led_controller.set_preset(2)

# Example Usage (Optional - for testing)
if __name__ == '__main__':
    # Configure logging for testing
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # --- IMPORTANT: Replace with your Hyperion's IP address ---
    HYPERION_IP = "localhost"  # Or "your_hyperion_ip_address"
    # HYPERION_IP = "192.168.1.100" # Example

    if HYPERION_IP == "localhost" and input("Did you change HYPERION_IP? (y/n): ").lower() != 'y':
        print("Please set HYPERION_IP to your Hyperion device's IP address in the __main__ block.")
    else:
        controller = LEDController(ip_address=HYPERION_IP)

        # Optional: If your Hyperion needs an auth token
        # token = "your_hyperion_auth_token_here"
        # controller.set_auth_token(token)

        print("--- Checking Hyperion Status ---")
        status = controller.check_wled_status()
        print(json.dumps(status, indent=2))

        if status.get("connected"):
            print("\n--- Setting Power ON ---")
            print(json.dumps(controller.set_power(1), indent=2)) # Turn ON
            time.sleep(1)

            print("\n--- Setting Brightness to 50% (WLED scale 128) ---")
            print(json.dumps(controller.set_brightness(128), indent=2))
            time.sleep(2)

            print("\n--- Setting Color to RED ---")
            print(json.dumps(controller.set_color(hex="#FF0000"), indent=2))
            time.sleep(2)

            print("\n--- Setting Color to GREEN ---")
            print(json.dumps(controller.set_color(r=0, g=255, b=0), indent=2))
            time.sleep(2)
            
            # --- Test an effect (ensure WLED_TO_HYPERION_EFFECT_MAP[47] is set) ---
            # For this to work, WLED_TO_HYPERION_EFFECT_MAP[47] must map to a valid Hyperion effect
            # that ideally uses "speed", "intensity", and "colors" (or "color") arguments.
            if 47 in WLED_TO_HYPERION_EFFECT_MAP:
                print(f"\n--- Setting Effect (WLED ID 47 -> Hyperion '{WLED_TO_HYPERION_EFFECT_MAP[47]}') ---")
                print(json.dumps(controller.set_effect(
                    effect_index=47,
                    speed=100,
                    intensity=200,
                    hex="#00FFFF", # Cyan
                    hex2="#FF00FF"  # Magenta
                ), indent=2))
                time.sleep(5)
            else:
                print("\nSkipping effect test: WLED effect ID 47 not mapped in WLED_TO_HYPERION_EFFECT_MAP.")

            # --- Test a preset (ensure WLED_TO_HYPERION_PRESET_MAP[1] is set) ---
            if 1 in WLED_TO_HYPERION_PRESET_MAP:
                print(f"\n--- Setting Preset (WLED ID 1 -> Hyperion '{WLED_TO_HYPERION_PRESET_MAP[1]}') ---")
                print(json.dumps(controller.set_preset(1), indent=2))
                time.sleep(5)
            else:
                print("\nSkipping preset test: WLED preset ID 1 not mapped in WLED_TO_HYPERION_PRESET_MAP.")


            print("\n--- Simulating effect_loading ---")
            if effect_loading(controller):
                print("effect_loading successful (Hyperion is ON)")
            else:
                print("effect_loading reported Hyperion as OFF or failed")
            time.sleep(5)

            print("\n--- Simulating effect_connected ---")
            if effect_connected(controller):
                 print("effect_connected successful (Hyperion is ON at end of sequence part)")
            else:
                print("effect_connected reported Hyperion as OFF or failed")
            # effect_connected already switches to idle at the end.

            print("\n--- Setting Power OFF ---")
            print(json.dumps(controller.set_power(0), indent=2)) # Turn OFF
        else:
            print(f"Could not connect to Hyperion at {HYPERION_IP} or other error occurred.")
