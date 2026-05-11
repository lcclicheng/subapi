"""A retro desktop Tank Battle game implemented with Tkinter.

Run with: python3 main.py
"""

from __future__ import annotations

import random
import tkinter as tk
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

TILE = 32
COLS = 26
ROWS = 20
WIDTH = COLS * TILE
HEIGHT = ROWS * TILE
BORDER = 10
WINDOW_WIDTH = WIDTH + BORDER * 2
WINDOW_HEIGHT = HEIGHT + BORDER * 2 + 48
TANK_SIZE = 26
BULLET_SIZE = 6
PLAYER_SPEED = 4
BULLET_SPEED = 9
WIN_SCORE = 18
POWERUP_TTL = 900
SKILL_TICKS = 600
FREEZE_TICKS = 360


class Direction(Enum):
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)

    @property
    def vector(self) -> tuple[int, int]:
        return self.value


class TileKind(Enum):
    BRICK = "brick"
    STEEL = "steel"
    FOREST = "forest"
    WATER = "water"


class PowerKind(Enum):
    SHIELD = "护盾"
    RAPID = "速射"
    FREEZE = "冰冻"
    BOMB = "炸弹"


@dataclass
class RectObject:
    x: int
    y: int
    size: int

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.size, self.y + self.size)


@dataclass
class Tile(RectObject):
    kind: TileKind


@dataclass
class Tank(RectObject):
    direction: Direction
    color: str
    reload_ticks: int = 0
    lives: int = 1
    speed: int = 2
    fire_chance: float = 0.012
    points: int = 1
    enemy_type: str = "普通"


@dataclass
class Bullet(RectObject):
    direction: Direction
    owner: str
    power: int = 1


@dataclass
class PowerUp(RectObject):
    kind: PowerKind
    ttl: int = POWERUP_TTL


class TankBattleGame:
    """Tkinter game loop, retro rendering, skills, and collision rules."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Tank Battle - 复古坦克大战")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(
            self.root,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            bg="#5c5c5c",
            highlightthickness=0,
        )
        self.canvas.pack()

        self.keys: set[str] = set()
        self.running = True
        self.game_over = False
        self.score = 0
        self.wave = 1
        self.shield_ticks = 0
        self.rapid_ticks = 0
        self.freeze_ticks = 0

        self.player = self._new_player()
        self.enemies: list[Tank] = []
        self.bullets: list[Bullet] = []
        self.powerups: list[PowerUp] = []
        self.tiles = self._build_tiles()
        self.base = RectObject(BORDER + 12 * TILE, BORDER + 18 * TILE, TILE * 2)
        self._spawn_wave()

        self.root.bind("<KeyPress>", self._on_key_press)
        self.root.bind("<KeyRelease>", self._on_key_release)
        self.root.after(16, self._tick)

    def _new_player(self) -> Tank:
        return Tank(
            BORDER + 12 * TILE + 3,
            BORDER + 16 * TILE + 3,
            TANK_SIZE,
            Direction.UP,
            "#f1b63a",
            lives=3,
            speed=PLAYER_SPEED,
        )

    def _build_tiles(self) -> list[Tile]:
        layout = [
            "..........................",
            "..b..s............ff......",
            "..b..s.......bb..b.ff..bff",
            "..b..s.......bf..b.ff..bff",
            "..bb....bb...ff..b.ff.bbff",
            "........bb..ss...bb....bff",
            "..bbb.....f.bbb..bb..bb...",
            "..........f.bbb.......bb..",
            "..bbbb..b.fffff..bb..bbb..",
            ".....ww...fffff..........f",
            "bbbwwwwbb..fff..bb.bbbbbff",
            "ssbbb..........bb....sssff",
            "..b....bb....bb..........f",
            "..bb...bb..........bbfffff",
            "...bbb........b.....bfffff",
            "....b.....ssss......b..b..",
            "..........s..s........b...",
            ".....b....s..s.....b......",
            "...........bb......b......",
            "....bb.....bb......b......",
        ]
        tiles: list[Tile] = []
        mapping = {
            "b": TileKind.BRICK,
            "s": TileKind.STEEL,
            "f": TileKind.FOREST,
            "w": TileKind.WATER,
        }
        for row, line in enumerate(layout):
            for col, char in enumerate(line):
                kind = mapping.get(char)
                if kind:
                    tiles.append(Tile(BORDER + col * TILE, BORDER + row * TILE, TILE, kind))
        return tiles

    def _spawn_wave(self) -> None:
        spawn_points = [
            (BORDER + TILE, BORDER + TILE),
            (BORDER + 12 * TILE, BORDER + TILE),
            (BORDER + 23 * TILE, BORDER + TILE),
            (BORDER + TILE, BORDER + 9 * TILE),
        ]
        random.shuffle(spawn_points)
        needed = min(2 + self.wave, 6)
        for index, (x, y) in enumerate(spawn_points[:needed]):
            self.enemies.append(self._make_enemy(x + 3, y + 3, index))

    def _make_enemy(self, x: int, y: int, index: int) -> Tank:
        roll = (self.wave + index + random.randrange(3)) % 4
        if roll == 1:
            return Tank(x, y, TANK_SIZE, Direction.DOWN, "#e8e8e8", lives=1, speed=3, fire_chance=0.014, points=1, enemy_type="快速")
        if roll == 2:
            return Tank(x, y, TANK_SIZE, Direction.DOWN, "#d34b36", lives=2, speed=1, fire_chance=0.012, points=2, enemy_type="重甲")
        if roll == 3:
            return Tank(x, y, TANK_SIZE, Direction.DOWN, "#7fd7ff", lives=1, speed=2, fire_chance=0.022, points=2, enemy_type="炮手")
        return Tank(x, y, TANK_SIZE, Direction.DOWN, "#f0f0f0", lives=1, speed=2, fire_chance=0.012, points=1, enemy_type="普通")

    def _on_key_press(self, event: tk.Event) -> None:
        key = event.keysym.lower()
        self.keys.add(key)
        if key == "r" and self.game_over:
            self._reset()

    def _on_key_release(self, event: tk.Event) -> None:
        self.keys.discard(event.keysym.lower())

    def _reset(self) -> None:
        self.game_over = False
        self.running = True
        self.score = 0
        self.wave = 1
        self.shield_ticks = 0
        self.rapid_ticks = 0
        self.freeze_ticks = 0
        self.player = self._new_player()
        self.enemies.clear()
        self.bullets.clear()
        self.powerups.clear()
        self.tiles = self._build_tiles()
        self._spawn_wave()

    def _tick(self) -> None:
        if self.running:
            self._update_timers()
            self._update_player()
            self._update_powerups()
            self._update_enemies()
            self._update_bullets()
            self._check_wave()
            self._draw()
        self.root.after(16, self._tick)

    def _update_timers(self) -> None:
        self.shield_ticks = max(0, self.shield_ticks - 1)
        self.rapid_ticks = max(0, self.rapid_ticks - 1)
        self.freeze_ticks = max(0, self.freeze_ticks - 1)

    def _update_player(self) -> None:
        if self.player.reload_ticks > 0:
            self.player.reload_ticks -= 1

        direction_key_pairs = [
            ("up", Direction.UP), ("w", Direction.UP),
            ("down", Direction.DOWN), ("s", Direction.DOWN),
            ("left", Direction.LEFT), ("a", Direction.LEFT),
            ("right", Direction.RIGHT), ("d", Direction.RIGHT),
        ]
        for key, direction in direction_key_pairs:
            if key in self.keys:
                self.player.direction = direction
                self._move_tank(self.player, direction, self.player.speed)
                break

        if ("space" in self.keys or "j" in self.keys) and self.player.reload_ticks == 0:
            self._fire(self.player, "player")

    def _update_powerups(self) -> None:
        for powerup in list(self.powerups):
            powerup.ttl -= 1
            if powerup.ttl <= 0:
                self.powerups.remove(powerup)
                continue
            if self._collides(powerup.bounds, self.player.bounds):
                self._activate_powerup(powerup.kind)
                self.powerups.remove(powerup)

    def _activate_powerup(self, kind: PowerKind) -> None:
        if kind is PowerKind.SHIELD:
            self.shield_ticks = SKILL_TICKS
        elif kind is PowerKind.RAPID:
            self.rapid_ticks = SKILL_TICKS
        elif kind is PowerKind.FREEZE:
            self.freeze_ticks = FREEZE_TICKS
        elif kind is PowerKind.BOMB:
            destroyed = len(self.enemies)
            self.enemies.clear()
            self.score += destroyed

    def _update_enemies(self) -> None:
        if self.freeze_ticks > 0:
            return
        for enemy in list(self.enemies):
            if enemy.reload_ticks > 0:
                enemy.reload_ticks -= 1
            if random.random() < 0.032:
                enemy.direction = random.choice(list(Direction))
            moved = self._move_tank(enemy, enemy.direction, enemy.speed)
            if not moved:
                enemy.direction = random.choice(list(Direction))
            if random.random() < enemy.fire_chance and enemy.reload_ticks == 0:
                self._fire(enemy, "enemy")

    def _update_bullets(self) -> None:
        for bullet in list(self.bullets):
            dx, dy = bullet.direction.vector
            bullet.x += dx * BULLET_SPEED
            bullet.y += dy * BULLET_SPEED

            if not self._inside_playfield(bullet.bounds):
                self._remove_bullet(bullet)
                continue

            if self._handle_tile_hit(bullet):
                continue

            if bullet.owner == "player":
                target = self._first_collision(bullet, self.enemies)
                if target:
                    target.lives -= bullet.power
                    if target.lives <= 0:
                        self.enemies.remove(target)
                        self.score += target.points
                        self._maybe_drop_powerup(target)
                    self._remove_bullet(bullet)
            elif self._collides(bullet.bounds, self.player.bounds):
                self._remove_bullet(bullet)
                if self.shield_ticks <= 0:
                    self.player.lives -= 1
                    if self.player.lives <= 0:
                        self._finish(False)
            elif self._collides(bullet.bounds, self.base.bounds):
                self._remove_bullet(bullet)
                self._finish(False)

    def _handle_tile_hit(self, bullet: Bullet) -> bool:
        hit_tile = self._first_collision(bullet, self._solid_tiles())
        if not hit_tile:
            return False
        if hit_tile.kind is TileKind.BRICK or bullet.power >= 2:
            self.tiles.remove(hit_tile)
        self._remove_bullet(bullet)
        return True

    def _maybe_drop_powerup(self, enemy: Tank) -> None:
        if random.random() > 0.38:
            return
        kind = random.choice(list(PowerKind))
        x = self._clamp(enemy.x, BORDER, BORDER + WIDTH - TILE)
        y = self._clamp(enemy.y, BORDER, BORDER + HEIGHT - TILE)
        self.powerups.append(PowerUp(x, y, 24, kind))

    def _check_wave(self) -> None:
        if self.score >= WIN_SCORE:
            self._finish(True)
        elif not self.enemies:
            self.wave += 1
            self._spawn_wave()

    def _finish(self, won: bool) -> None:
        self.running = False
        self.game_over = True
        self._draw(won=won)

    def _move_tank(self, tank: Tank, direction: Direction, speed: int) -> bool:
        old_x, old_y = tank.x, tank.y
        dx, dy = direction.vector
        tank.x += dx * speed
        tank.y += dy * speed

        blockers: list[RectObject] = [*self._solid_tiles(), self.base]
        if tank is not self.player:
            blockers.append(self.player)
        blockers.extend(obj for obj in self.enemies if obj is not tank)

        if not self._inside_playfield(tank.bounds) or any(self._collides(tank.bounds, obj.bounds) for obj in blockers):
            tank.x, tank.y = old_x, old_y
            return False
        return True

    def _fire(self, tank: Tank, owner: str) -> None:
        dx, dy = tank.direction.vector
        center_x = tank.x + tank.size // 2 - BULLET_SIZE // 2
        center_y = tank.y + tank.size // 2 - BULLET_SIZE // 2
        power = 2 if owner == "player" and self.rapid_ticks > 0 else 1
        bullet = Bullet(
            center_x + dx * (tank.size // 2),
            center_y + dy * (tank.size // 2),
            BULLET_SIZE,
            tank.direction,
            owner,
            power,
        )
        self.bullets.append(bullet)
        if owner == "player":
            tank.reload_ticks = 10 if self.rapid_ticks > 0 else 24
        else:
            tank.reload_ticks = 52

    def _draw(self, won: bool | None = None) -> None:
        self.canvas.delete("all")
        self.canvas.create_rectangle(BORDER, BORDER, BORDER + WIDTH, BORDER + HEIGHT, fill="#020202", outline="#8f8f8f", width=3)
        self._draw_tiles(TileKind.WATER)
        self._draw_tiles(TileKind.BRICK)
        self._draw_tiles(TileKind.STEEL)
        self._draw_base()
        for powerup in self.powerups:
            self._draw_powerup(powerup)
        for bullet in self.bullets:
            color = "#fff76a" if bullet.owner == "player" else "#f4f4f4"
            self.canvas.create_rectangle(*bullet.bounds, fill=color, outline="")
        self._draw_tank(self.player, is_player=True)
        for enemy in self.enemies:
            self._draw_tank(enemy, is_player=False)
        self._draw_tiles(TileKind.FOREST)
        if self.shield_ticks > 0:
            self.canvas.create_oval(self.player.x - 5, self.player.y - 5, self.player.x + self.player.size + 5, self.player.y + self.player.size + 5, outline="#8be9fd", width=3)
        self._draw_hud()
        if self.game_over:
            message = "胜利！按 R 再来一局" if won else "基地被毁/生命耗尽！按 R 重开"
            self.canvas.create_rectangle(170, 245, WINDOW_WIDTH - 170, 390, fill="#111111", outline="#f7d154", width=4)
            self.canvas.create_text(WINDOW_WIDTH // 2, 295, fill="white", font=("Arial", 25, "bold"), text=message)
            self.canvas.create_text(WINDOW_WIDTH // 2, 340, fill="#d8d8d8", font=("Arial", 14), text=f"最终分数：{self.score}")

    def _draw_tiles(self, kind: TileKind) -> None:
        for tile in self.tiles:
            if tile.kind is not kind:
                continue
            if kind is TileKind.BRICK:
                self._draw_brick(tile)
            elif kind is TileKind.STEEL:
                self._draw_steel(tile)
            elif kind is TileKind.FOREST:
                self._draw_forest(tile)
            elif kind is TileKind.WATER:
                self._draw_water(tile)

    def _draw_brick(self, tile: Tile) -> None:
        self.canvas.create_rectangle(*tile.bounds, fill="#5e5e5e", outline="")
        brick_h = 8
        colors = ("#ff2c16", "#d91c0d")
        for row in range(4):
            offset = 0 if row % 2 == 0 else TILE // 2
            y = tile.y + row * brick_h + 1
            for x in range(tile.x - offset, tile.x + TILE, TILE // 2):
                self.canvas.create_rectangle(x + 1, y, x + TILE // 2 - 2, y + brick_h - 2, fill=colors[row % 2], outline="#ffb25c")

    def _draw_steel(self, tile: Tile) -> None:
        self.canvas.create_rectangle(*tile.bounds, fill="#f4f4f4", outline="#777777")
        pad = 4
        self.canvas.create_polygon(tile.x + pad, tile.y + TILE - pad, tile.x + TILE - pad, tile.y + pad, tile.x + TILE - pad, tile.y + TILE - pad, fill="#c9c9c9", outline="")
        self.canvas.create_line(tile.x + pad, tile.y + TILE - pad, tile.x + TILE - pad, tile.y + pad, fill="#ffffff", width=2)

    def _draw_forest(self, tile: Tile) -> None:
        self.canvas.create_rectangle(*tile.bounds, fill="#7ef35f", outline="")
        colors = ("#0f7d28", "#1fa83a", "#d3ff6a")
        for row in range(4):
            for col in range(4):
                offset = ((tile.x // TILE + tile.y // TILE + row * 3 + col * 5) % 6) - 2
                x = tile.x + col * 8 + 2 + offset
                y = tile.y + row * 8 + 2 - offset
                color = colors[(row + col + tile.x // TILE) % len(colors)]
                self.canvas.create_rectangle(x, y, x + 5, y + 5, fill=color, outline="")

    def _draw_water(self, tile: Tile) -> None:
        self.canvas.create_rectangle(*tile.bounds, fill="#0b3d91", outline="")
        for y in range(tile.y + 6, tile.y + TILE, 10):
            self.canvas.create_line(tile.x + 4, y, tile.x + TILE - 4, y + 3, fill="#62d8ff", width=2)

    def _draw_base(self) -> None:
        x, y, _, _ = self.base.bounds
        self.canvas.create_rectangle(*self.base.bounds, fill="#dedede", outline="#777777", width=2)
        self.canvas.create_polygon(x + 12, y + 45, x + 32, y + 16, x + 52, y + 45, fill="#303030", outline="#000000")
        self.canvas.create_line(x + 24, y + 34, x + 32, y + 42, x + 40, y + 34, fill="#ff3030", width=3)

    def _draw_powerup(self, powerup: PowerUp) -> None:
        colors = {
            PowerKind.SHIELD: "#60d7ff",
            PowerKind.RAPID: "#ffe66d",
            PowerKind.FREEZE: "#a7f3ff",
            PowerKind.BOMB: "#ff5f5f",
        }
        labels = {
            PowerKind.SHIELD: "S",
            PowerKind.RAPID: "R",
            PowerKind.FREEZE: "F",
            PowerKind.BOMB: "B",
        }
        self.canvas.create_rectangle(*powerup.bounds, fill=colors[powerup.kind], outline="white", width=2)
        self.canvas.create_text(powerup.x + powerup.size // 2, powerup.y + powerup.size // 2, text=labels[powerup.kind], fill="#111111", font=("Arial", 12, "bold"))

    def _draw_tank(self, tank: Tank, is_player: bool) -> None:
        x, y, size = tank.x, tank.y, tank.size
        track = "#f5e6a0" if is_player else "#d6f4ff"
        self.canvas.create_rectangle(x, y + 3, x + 5, y + size - 3, fill=track, outline="#777777")
        self.canvas.create_rectangle(x + size - 5, y + 3, x + size, y + size - 3, fill=track, outline="#777777")
        self.canvas.create_rectangle(x + 6, y + 5, x + size - 6, y + size - 5, fill=tank.color, outline="#2b2b2b", width=2)
        dx, dy = tank.direction.vector
        cx = x + size // 2
        cy = y + size // 2
        self.canvas.create_line(cx, cy, cx + dx * 21, cy + dy * 21, fill="#f8f8f8", width=5, capstyle=tk.PROJECTING)
        self.canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill="#fffdf0", outline="#333333")
        if not is_player and tank.lives > 1:
            self.canvas.create_text(cx, y - 4, fill="#ffdf5d", font=("Arial", 9, "bold"), text=str(tank.lives))

    def _draw_hud(self) -> None:
        y = BORDER + HEIGHT + 8
        skills: list[str] = []
        if self.shield_ticks > 0:
            skills.append(f"护盾 {self.shield_ticks // 60 + 1}s")
        if self.rapid_ticks > 0:
            skills.append(f"速射 {self.rapid_ticks // 60 + 1}s")
        if self.freeze_ticks > 0:
            skills.append(f"冰冻 {self.freeze_ticks // 60 + 1}s")
        skill_text = " · ".join(skills) if skills else "拾取 S/R/F/B 方块获得技能"
        hud = f"生命 {self.player.lives}   分数 {self.score}/{WIN_SCORE}   波次 {self.wave}   {skill_text}"
        self.canvas.create_text(BORDER, y, anchor="nw", fill="white", font=("Arial", 13, "bold"), text=hud)
        self.canvas.create_text(WINDOW_WIDTH - BORDER, y, anchor="ne", fill="#e6e6e6", font=("Arial", 11), text="WASD/方向键移动 · 空格/J 射击 · R 重开")

    def _solid_tiles(self) -> list[Tile]:
        return [tile for tile in self.tiles if tile.kind in {TileKind.BRICK, TileKind.STEEL, TileKind.WATER}]

    def _first_collision(self, item: RectObject, targets: Iterable[RectObject]) -> RectObject | None:
        for target in targets:
            if self._collides(item.bounds, target.bounds):
                return target
        return None

    def _remove_bullet(self, bullet: Bullet) -> None:
        if bullet in self.bullets:
            self.bullets.remove(bullet)

    @staticmethod
    def _inside_playfield(bounds: tuple[int, int, int, int]) -> bool:
        left, top, right, bottom = bounds
        return left >= BORDER and top >= BORDER and right <= BORDER + WIDTH and bottom <= BORDER + HEIGHT

    @staticmethod
    def _collides(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
        return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]

    @staticmethod
    def _clamp(value: int, low: int, high: int) -> int:
        return max(low, min(value, high))

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    TankBattleGame().run()
