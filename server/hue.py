import requests
import logging
import urllib3
import concurrent.futures
from typing import Optional, Dict, Any, List
from config import BASE_URL, DEFAULT_BRI, HUE_USERNAME, GEMINI_COLORS_XY
from color_utils import hue_sat_to_xy

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("lightshow")

class HueController:
    _session = requests.Session()
    if HUE_USERNAME:
        _session.headers.update({"hue-application-key": HUE_USERNAME})
    _group0_id = None
    _executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

    @staticmethod
    def _make_request(method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Optional[requests.Response]:
        """Helper to make safe HTTP requests to the Hue Bridge using V2 API."""
        url = f"{BASE_URL}/{endpoint}"
        try:
            if method == "GET":
                resp = HueController._session.get(url, timeout=2, verify=False)
            elif method == "PUT":
                resp = HueController._session.put(url, json=data, timeout=0.5, verify=False)
            else:
                logger.error(f"Unsupported HTTP method: {method}")
                return None
            
            resp.raise_for_status()
            
            if method == "PUT":
                logger.debug(f"Hue {method} {endpoint}: {resp.status_code}")
            return resp
        except requests.RequestException as e:
            logger.error(f"Hue Request Failed ({endpoint}): {e}")
            return None

    @staticmethod
    def get_lights() -> List[str]:
        resp = HueController._make_request("GET", "resource/light")
        if resp:
            data = resp.json().get("data", [])
            return [l["id"] for l in data]
        return []

    @staticmethod
    def set_state(light_id: str, state: Dict[str, Any]) -> None:
        """Sends a state update to a specific light using V2 standard asynchronously."""
        HueController._executor.submit(HueController._make_request, "PUT", f"resource/light/{light_id}", state)

    @staticmethod
    def _get_group0_id() -> Optional[str]:
        if HueController._group0_id:
            return HueController._group0_id
        resp = HueController._make_request("GET", "resource/grouped_light")
        if resp:
            data = resp.json().get("data", [])
            for group in data:
                if group.get("id_v1") == "/groups/0":
                    HueController._group0_id = group["id"]
                    return group["id"]
        return None

    @staticmethod
    def set_group_state(state: Dict[str, Any]) -> None:
        """Sets the state for all lights (Group 0 is usually 'All') using V2 standard asynchronously."""
        group_id = HueController._get_group0_id()
        if group_id:
            HueController._executor.submit(HueController._make_request, "PUT", f"resource/grouped_light/{group_id}", state)
        else:
            logger.error("Could not find group 0 in V2 API")

    @staticmethod
    def set_gemini_gradient(bri: int = 150) -> None:
        """Sets the lights to a Gemini CLI logo gradient concurrently."""
        try:
            resp = HueController._make_request("GET", "resource/light")
            if not resp:
                logger.error("Could not retrieve lights from Hue bridge.")
                return
            lights_data = resp.json().get("data", [])
            
            def update_light(i, light):
                light_id = light["id"]
                state = {
                    "on": {"on": True},
                    "dimming": {"brightness": (bri / 254.0) * 100.0}
                }
                if "gradient" in light:
                    points_capable = light["gradient"].get("points_capable", 5)
                    points = [
                        {"color": {"xy": {"x": x, "y": y}}} for x, y in GEMINI_COLORS_XY[:points_capable]
                    ]
                    state["gradient"] = {"points": points}
                else:
                    x, y = GEMINI_COLORS_XY[i % len(GEMINI_COLORS_XY)]
                    state["color"] = {"xy": {"x": x, "y": y}}
                    
                HueController._make_request("PUT", f"resource/light/{light_id}", state)

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(update_light, i, light) for i, light in enumerate(lights_data)]
                concurrent.futures.wait(futures)
                
        except Exception as e:
            logger.error(f"Failed to set Gemini gradient: {e}")

    @staticmethod
    def turn_off() -> None:
        """FORCE RESET: Clear any previous effects and turn OFF lights synchronously."""
        logger.info("Clearing previous effects and turning OFF lights...")
        state = {
            "on": {"on": False}, 
            "dimming": {"brightness": 100.0}, 
            "dynamics": {"duration": 0}
        }
        group_id = HueController._get_group0_id()
        if group_id:
            HueController._make_request("PUT", f"resource/grouped_light/{group_id}", state)
        else:
            logger.error("Could not find group 0 in V2 API")

    @staticmethod
    def turn_on() -> None:
        """Reset lights to ON, clear effects, set default brightness and white color."""
        logger.info("Resetting lights to ON, White, and clearing effects...")
        x, y = hue_sat_to_xy(0, 0)
        HueController.set_group_state({
            "on": {"on": True}, 
            "dimming": {"brightness": (DEFAULT_BRI / 254.0) * 100.0}, 
            "color": {"xy": {"x": x, "y": y}}
        })