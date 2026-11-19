"""Read annotated Bambu Studio and Orca G-code without executing it."""

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

MOTION = re.compile(r"^([GMT]\d+)(?=\s|[A-Z]|$)")
AXES = re.compile(r"([XYZE])\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))")
CONFIG = re.compile(r"; ([a-z_]+) = (.*)")
PROFILE_KEYS = {
    "printer_model",
    "printer_settings_id",
    "print_settings_id",
    "filament_settings_id",
    "filament_type",
    "filament_diameter",
    "nozzle_diameter",
    "wall_generator",
    "layer_height",
    "line_width",
    "outer_wall_line_width",
    "inner_wall_line_width",
}
MODEL = {
    "outer wall",
    "inner wall",
    "overhang wall",
    "floating vertical shell",
    "bridge",
    "internal bridge",
    "sparse infill",
    "internal solid infill",
    "top surface",
    "bottom surface",
    "gap infill",
    "gap fill",
    "iron",
    "ironing",
    "overhang perimeter",
    "external perimeter",
    "perimeter",
    "internal infill",
    "solid infill",
    "top solid infill",
    "bridge infill",
    "internal bridge infill",
    "thin wall",
}
SUPPORT = {
    "support",
    "support interface",
    "support material",
    "support material interface",
    "support transition",
    "raft",
    "raft interface",
}
AUXILIARY = {
    "custom",
    "prime tower",
    "wipe tower",
    "skirt",
    "brim",
    "skirt/brim",
    "purge",
    "none",
    "mixed",
    "iron",
    "ironing",
}
WALLS = {
    "outer wall",
    "inner wall",
    "external perimeter",
    "perimeter",
    "thin wall",
    "gap infill",
    "gap fill",
}


def role_group(role):
    if role in SUPPORT:
        return "support"
    if "bridge" in role:
        return "bridge"
    if role in {"overhang wall", "overhang perimeter", "floating vertical shell"}:
        return "overhang"
    if role in WALLS:
        return "wall"
    return "model"


@dataclass(frozen=True, slots=True)
class Segment:
    start: tuple[float, float]
    end: tuple[float, float]
    z: float
    role: str
    length: float
    width: float | None
    line: int


class Toolpaths:
    """Only explicit, planar extrusion with a recognized feature role is evidence."""

    def __init__(self, text):
        self.profile = {}
        self.issues = Counter()
        self.layer_issues = defaultdict(Counter)
        self.model_layers = set()
        self.support_layers = set()
        self.counts = Counter()
        self.longest_run = {}
        self.longest_segment = {}
        self.wall_widths = {}
        lines = text.splitlines()
        self.version = next(
            (
                line.lstrip("; ").strip()
                for line in lines[:16]
                if "BambuStudio" in line or "OrcaSlicer" in line
            ),
            None,
        )
        self.bounded = "; EXECUTABLE_BLOCK_START" in text and "; EXECUTABLE_BLOCK_END" in text
        self.lines = lines
        self.diameter = None
        # Equal diameters avoid guessing the active filament across vendor tool remaps.
        in_config = False
        for line in lines:
            if line == "; CONFIG_BLOCK_START":
                in_config = True
            elif line == "; CONFIG_BLOCK_END":
                in_config = False
            elif in_config:
                match = CONFIG.fullmatch(line)
                if match and match[1] in PROFILE_KEYS:
                    self.profile[match[1]] = match[2]
        try:
            diameters = {float(v) for v in self.profile.get("filament_diameter", "").split(",")}
            if len(diameters) == 1:
                diameter = diameters.pop()
                if math.isfinite(diameter) and diameter > 0:
                    self.diameter = diameter
        except ValueError:
            pass

    def segments(self):
        if not self.version or not self.bounded:
            self.issues["missing recognized slicer header or executable block"] += 1
            return
        active = skipped = skip_moves = False
        absolute_xyz = True
        relative_e = None
        position = dict.fromkeys("XYZ", None)
        e = 0.0
        debt = 0.0
        role = "custom"
        z = height = None
        run = 0.0
        for line_number, line in enumerate(self.lines, 1):
            line = line.strip()
            if line == "; EXECUTABLE_BLOCK_START":
                active = True
                continue
            if line == "; EXECUTABLE_BLOCK_END":
                break
            if not active:
                continue
            if line == "; SKIPPABLE_START":
                skipped = True
                skip_moves = False
                continue
            elif line == "; SKIPPABLE_END":
                skipped = False
                # The next model move needs an explicit positional anchor.
                if skip_moves:
                    position = dict.fromkeys("XYZ", None)
                    run = 0.0
                continue
            if skipped:
                op = MOTION.match(line)
                if op and op[1] in {"G0", "G1", "G2", "G3", "G28", "G92"}:
                    skip_moves = True
                continue
            if line == "; CHANGE_LAYER":
                z = height = None
                role = "custom"
                run = 0.0
            elif line.startswith(("; Z_HEIGHT:", "; LAYER_HEIGHT:")):
                key, value = line.split(":", 1)
                try:
                    number = float(value)
                    if not math.isfinite(number) or number <= 0:
                        raise ValueError
                    if key == "; Z_HEIGHT":
                        z = round(number, 6)
                    else:
                        height = number
                except ValueError:
                    self.issues["invalid layer annotation"] += 1
            elif line.startswith("; FEATURE:"):
                role = line.split(":", 1)[1].strip().lower()
                run = 0.0

            command = line.partition(";")[0].rstrip()
            match = MOTION.match(command)
            if not match:
                continue
            op = match[1]
            if op in {"G90", "G91"}:
                absolute_xyz = op == "G90"
                continue
            if op in {"M82", "M83"}:
                relative_e = op == "M83"
                continue
            if op in {
                "G20",
                "M200",
                "G10",
                "G11",
                "G54",
                "G55",
                "G56",
                "G57",
                "G58",
                "G59",
                "M206",
                "M218",
            }:
                self.issues[f"unsupported command {op}"] += 1
                continue
            if op.startswith("T"):
                if relative_e is False and z is not None:
                    self.layer_issues[z]["absolute E across tool change is unsupported"] += 1
                run = 0.0
                continue
            if op == "G28":
                position = dict.fromkeys("XYZ", None)
                continue
            if op not in {"G0", "G1", "G2", "G3", "G92"}:
                continue
            axes = {key: float(value) for key, value in AXES.findall(command[match.end() :])}
            if not all(math.isfinite(value) for value in axes.values()):
                self.issues["invalid motion coordinate"] += 1
                continue
            if op == "G92":
                if "E" in axes:
                    e = axes["E"]
                if axes.keys() & position.keys():
                    self.issues["unsupported XYZ coordinate reset"] += 1
                continue
            start = tuple(position.values())
            for axis in position.keys() & axes.keys():
                if absolute_xyz:
                    position[axis] = axes[axis]
                elif position[axis] is not None:
                    position[axis] += axes[axis]
            end = tuple(position.values())
            if "E" not in axes:
                if start != end or op in {"G2", "G3"}:
                    run = 0.0
                continue
            if relative_e is None:
                if z is not None and role not in AUXILIARY:
                    self.layer_issues[z]["extrusion mode is unknown"] += 1
                continue
            delta = axes["E"] if relative_e else axes["E"] - e
            if not relative_e:
                e = axes["E"]
            available = max(0.0, delta - debt)
            debt = max(0.0, debt - delta)
            if available > 0 and z is None and role not in AUXILIARY:
                self.issues["feature extrusion lacks a valid layer annotation"] += 1
            if available <= 0 or z is None or role in AUXILIARY:
                run = 0.0
                continue
            if role not in MODEL and role not in SUPPORT:
                self.layer_issues[z][f"unrecognized extrusion role: {role}"] += 1
                continue
            if op in {"G2", "G3"}:
                self.layer_issues[z]["arc extrusion is unsupported"] += 1
                continue
            if None in (*start[:2], *end[:2]):
                self.layer_issues[z]["extrusion position is unknown"] += 1
                continue
            length = math.dist(start[:2], end[:2])
            if length == 0:
                continue
            if start[2] != end[2] or end[2] is None:
                self.layer_issues[z]["nonplanar or unknown extrusion Z"] += 1
                continue
            # Feature-specific bridge/support extrusion height can differ from model layer height.
            # Absolute executable Z still needs to agree with the layer label for witness checks.
            if abs(end[2] - z) > 0.001 and role not in SUPPORT:
                self.layer_issues[z]["extrusion Z disagrees with layer label"] += 1
                continue
            if available < delta:
                fraction = (delta - available) / delta
                start = tuple(a + (b - a) * fraction for a, b in zip(start[:2], end[:2]))
                length = math.dist(start, end[:2])
                if not length:
                    continue
            group = role_group(role)
            width = None
            if height and self.diameter:
                area = math.pi * (self.diameter / 2) ** 2
                width = available * area / (length * height)
                if not math.isfinite(width):
                    width = None
            self.counts[group] += 1
            run += length
            if length > self.longest_segment.get(group, (0,))[0]:
                self.longest_segment[group] = (length, line_number, start[:2], end[:2], end[2])
            if run > self.longest_run.get(group, (0, 0, 0))[0]:
                self.longest_run[group] = (run, z, line_number)
            if group == "support":
                self.support_layers.add(round(end[2], 6))
            else:
                self.model_layers.add(z)
            if group == "wall" and width is not None:
                low, high = self.wall_widths.get(role, (width, width))
                self.wall_widths[role] = (min(low, width), max(high, width))

            yield Segment(start[:2], end[:2], round(end[2], 6), role, length, width, line_number)
