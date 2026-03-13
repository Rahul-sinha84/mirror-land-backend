"""
Level JSON validator and auto-fixer.

Runs 9 checks against game world constraints and auto-fixes issues so that
every level sent to the frontend is guaranteed playable.
"""

import logging

logger = logging.getLogger(__name__)

GROUND_Y = 850
GROUND_H = 230
PLAYER_W = 48
PLAYER_H = 64
DEFAULT_PLATFORM_H = 48

MAX_GAP = 250
MAX_GAP_DOUBLE = 350
MAX_HEIGHT_DIFF = 160
MAX_HEIGHT_DIFF_DOUBLE = 300

MIN_WORLD_W = 2000
WORLD_H = 1080

GRAVITY_RANGE = (800, 1600)
JUMP_FORCE_RANGE = (-900, -400)
MOVE_SPEED_RANGE = (150, 500)


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def ensure_ground_exists(level: dict) -> None:
    platforms = level.setdefault("platforms", [])
    has_ground = any(p.get("role") == "ground" for p in platforms)
    if not has_ground:
        world_w = level.get("world", {}).get("width", 3840)
        platforms.insert(0, {
            "x": 0, "y": GROUND_Y, "w": world_w, "h": GROUND_H,
            "role": "ground", "color": "#3d2b1f",
        })
        logger.warning("Inserted missing ground platform (0-%d)", world_w)


def fix_player_spawn(level: dict) -> None:
    spawn = level.setdefault("player_spawn", {})
    grounds = [p for p in level.get("platforms", []) if p.get("role") == "ground"]
    if not grounds:
        spawn.setdefault("x", 60)
        spawn.setdefault("y", GROUND_Y - PLAYER_H - 6)
        return
    first = min(grounds, key=lambda p: p["x"])
    spawn.setdefault("x", first["x"] + 60)
    spawn["y"] = first["y"] - PLAYER_H - 6


def fix_unreachable_platforms(level: dict, double_jump: bool) -> None:
    max_h = MAX_HEIGHT_DIFF_DOUBLE if double_jump else MAX_HEIGHT_DIFF
    max_g = MAX_GAP_DOUBLE if double_jump else MAX_GAP
    platforms = level.get("platforms", [])
    floating = sorted(
        [p for p in platforms if p.get("role") != "ground"],
        key=lambda p: p["x"],
    )
    for i in range(1, len(floating)):
        prev, cur = floating[i - 1], floating[i]
        gap_x = cur["x"] - (prev["x"] + prev.get("w", 192))
        diff_y = abs(cur["y"] - prev["y"])
        if gap_x > max_g or diff_y > max_h:
            bridge_x = prev["x"] + prev.get("w", 192) + gap_x // 2 - 96
            bridge_y = min(prev["y"], cur["y"]) + diff_y // 2
            platforms.append({
                "x": bridge_x, "y": bridge_y, "w": 192, "h": DEFAULT_PLATFORM_H,
                "role": "platform",
            })
            logger.warning("Inserted bridge platform at (%d, %d)", bridge_x, bridge_y)


def fix_ground_gaps(level: dict, double_jump: bool) -> None:
    max_g = MAX_GAP_DOUBLE if double_jump else MAX_GAP
    grounds = sorted(
        [p for p in level.get("platforms", []) if p.get("role") == "ground"],
        key=lambda p: p["x"],
    )
    for i in range(1, len(grounds)):
        prev, cur = grounds[i - 1], grounds[i]
        prev_end = prev["x"] + prev.get("w", 192)
        gap = cur["x"] - prev_end
        if gap > max_g:
            extend = gap - max_g + 10
            prev["w"] = prev.get("w", 192) + extend
            logger.warning("Extended ground segment to close gap (%d -> %d)", gap, gap - extend)


def fix_enemy_placement(level: dict) -> None:
    grounds = [p for p in level.get("platforms", []) if p.get("role") == "ground"]
    all_platforms = level.get("platforms", [])
    for enemy in level.get("enemies", []):
        ex, ey = enemy.get("x", 0), enemy.get("y", 0)
        best = None
        best_dist = float("inf")
        for p in all_platforms:
            surface_y = p["y"] - PLAYER_H + 6
            if p["x"] <= ex <= p["x"] + p.get("w", 192):
                dist = abs(ey - surface_y)
                if dist < best_dist:
                    best_dist = dist
                    best = surface_y
        if best is not None and best_dist > 20:
            enemy["y"] = best
            logger.warning("Snapped enemy at x=%d to y=%d", ex, best)
        elif best is None and grounds:
            g = min(grounds, key=lambda p: abs(p["x"] + p.get("w", 192) // 2 - ex))
            enemy["y"] = g["y"] - PLAYER_H + 6
            logger.warning("Moved floating enemy at x=%d to ground", ex)


def fix_mission_requirements(level: dict) -> None:
    mission = level.get("mission", {})
    m_type = mission.get("type", "reach_exit")
    target = mission.get("target_count", 0)
    pickups = level.setdefault("pickups", [])
    enemies = level.setdefault("enemies", [])

    if m_type == "find_key_exit":
        keys = [p for p in pickups if p.get("role") == "key"]
        if not keys:
            world_w = level.get("world", {}).get("width", 3840)
            pickups.append({"role": "key", "x": world_w * 2 // 3, "y": GROUND_Y - 40})
            logger.warning("Added missing key pickup for find_key_exit mission")

    elif m_type == "collect_all":
        coins = [p for p in pickups if p.get("role") == "coin"]
        while len(coins) < target:
            x = 200 + len(coins) * 120
            pickups.append({"role": "coin", "x": x, "y": GROUND_Y - 32})
            coins.append(pickups[-1])
            logger.warning("Added coin to meet collect_all target (%d/%d)", len(coins), target)

    elif m_type == "kill_all":
        if len(enemies) < target:
            mission["target_count"] = len(enemies)
            logger.warning("Adjusted kill_all target_count from %d to %d", target, len(enemies))
        elif len(enemies) > target:
            mission["target_count"] = len(enemies)


def fix_exit_placement(level: dict) -> None:
    exit_obj = level.get("exit")
    platforms = level.get("platforms", [])
    world_w = level.get("world", {}).get("width", 3840)

    if not exit_obj:
        level["exit"] = {
            "role": "exit_door", "x": world_w - 200, "y": GROUND_Y - 192,
            "w": 128, "h": 192,
            "unlock_condition": "none",
            "locked_dialogue": "The exit is sealed.",
            "target_level": "level_002",
        }
        logger.warning("Added missing exit at x=%d", world_w - 200)
        return

    ex = exit_obj.get("x", 0)
    on_platform = any(
        p["x"] <= ex <= p["x"] + p.get("w", 192)
        for p in platforms
    )
    if not on_platform and platforms:
        rightmost = max(platforms, key=lambda p: p["x"] + p.get("w", 192))
        exit_obj["x"] = rightmost["x"] + rightmost.get("w", 192) - 150
        exit_obj["y"] = rightmost["y"] - 192
        logger.warning("Moved exit to sit on rightmost platform")


def clamp_world_bounds(level: dict) -> None:
    world = level.setdefault("world", {})
    world["width"] = max(world.get("width", 3840), MIN_WORLD_W)
    world["height"] = WORLD_H
    w = world["width"]

    for collection in ("platforms", "pickups", "enemies", "blocks", "hazards",
                       "bounce_pads", "teleporters", "npcs"):
        for entity in level.get(collection, []):
            if "x" in entity:
                entity["x"] = _clamp(entity["x"], 0, w - entity.get("w", 48))
            if "y" in entity:
                entity["y"] = _clamp(entity["y"], 0, WORLD_H - entity.get("h", 48))


def clamp_physics(level: dict) -> None:
    phys = level.setdefault("physics", {})
    phys["gravity"] = _clamp(phys.get("gravity", 1200), *GRAVITY_RANGE)
    phys["jump_force"] = _clamp(phys.get("jump_force", -700), *JUMP_FORCE_RANGE)
    phys["move_speed"] = _clamp(phys.get("move_speed", 300), *MOVE_SPEED_RANGE)
    phys.setdefault("max_fall_speed", 600)
    phys.setdefault("friction", 800)
    phys.setdefault("coyote_time_ms", 80)
    phys.setdefault("jump_buffer_ms", 100)


def validate_and_fix_level(level: dict) -> dict:
    """Run all 9 validation checks and return the fixed level."""
    double_jump = level.get("mechanics", {}).get("double_jump", False)

    ensure_ground_exists(level)
    fix_player_spawn(level)
    fix_unreachable_platforms(level, double_jump)
    fix_ground_gaps(level, double_jump)
    fix_enemy_placement(level)
    fix_mission_requirements(level)
    fix_exit_placement(level)
    clamp_world_bounds(level)
    clamp_physics(level)

    return level
