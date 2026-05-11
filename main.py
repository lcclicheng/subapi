"""A small desktop Tank Battle game implemented with Tkinter.

Run with: python3 main.py
"""

from __future__ import annotations

import random
import tkinter as tk
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

WIDTH = 800
HEIGHT = 600
TILE = 40
TANK_SIZE = 32
BULLET_SIZE = 6
PLAYER_SPEED = 5
ENEMY_SPEED = 2
BULLET_SPEED = 10
ENEMY_FIRE_CHANCE = 0.018
ENEMY_TURN_CHANCE = 0.03
WIN_SCORE = 10


class Direction(Enum):
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)

    @property
    def vector(self) -> tuple[int, int]:
        return self.value


@dataclass
class RectObject:
    x: int
    y: int
    size: int

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.size, self.y + self.size)


@dataclass
class Tank(RectObject):
    direction: Direction
    color: str
    reload_ticks: int = 0
    lives: int = 1


@dataclass
class Bullet(RectObject):
    direction: Direction
    owner: str


class TankBattleGame:
    """Tkinter game loop and collision rules for a simple tank shooter."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Tank Battle - 桌面坦克大战")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(self.root, width=WIDTH, height=HEIGHT, bg="#20242b")
        self.canvas.pack()

        self.keys: set[str] = set()
        self.running = True
        self.game_over = False
        self.score = 0
        self.wave = 1

        self.player = Tank(WIDTH // 2 - TANK_SIZE // 2, HEIGHT - 70, TANK_SIZE, Direction.UP, "#45d483", lives=3)
        self.enemies: list[Tank] = []
        self.bullets: list[Bullet] = []
        self.walls = self._build_walls()
        self._spawn_wave()

        self.root.bind("<KeyPress>", self._on_key_press)
        self.root.bind("<KeyRelease>", self._on_key_release)
        self.root.after(16, self._tick)

    def _build_walls(self) -> list[RectObject]:
        layout = [
            (4, 3), (5, 3), (12, 3), (13, 3),
            (2, 6), (3, 6), (8, 6), (9, 6), (16, 6),
            (6, 9), (7, 9), (12, 9), (13, 9),
            (3, 12), (4, 12), (15, 12), (16, 12),
        ]
        return [RectObject(col * TILE, row * TILE, TILE) for col, row in layout]

    def _spawn_wave(self) -> None:
        spawn_points = [(60, 50), (WIDTH // 2 - 20, 50), (WIDTH - 95, 50)]
        random.shuffle(spawn_points)
        needed = min(2 + self.wave, 5)
        for x, y in spawn_points[:needed]:
            self.enemies.append(Tank(x, y, TANK_SIZE, Direction.DOWN, "#ef5b5b"))

    def _on_key_press(self, event: tk.Event) -> None:
        self.keys.add(event.keysym.lower())
        if event.keysym.lower() == "r" and self.game_over:
            self._reset()

    def _on_key_release(self, event: tk.Event) -> None:
        self.keys.discard(event.keysym.lower())

    def _reset(self) -> None:
        self.game_over = False
        self.running = True
        self.score = 0
        self.wave = 1
        self.player = Tank(WIDTH // 2 - TANK_SIZE // 2, HEIGHT - 70, TANK_SIZE, Direction.UP, "#45d483", lives=3)
        self.enemies.clear()
        self.bullets.clear()
        self._spawn_wave()

    def _tick(self) -> None:
        if self.running:
            self._update_player()
            self._update_enemies()
            self._update_bullets()
            self._check_wave()
            self._draw()
        self.root.after(16, self._tick)

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
                self._move_tank(self.player, direction, PLAYER_SPEED)
                break

        if ("space" in self.keys or "j" in self.keys) and self.player.reload_ticks == 0:
            self._fire(self.player, "player")

    def _update_enemies(self) -> None:
        for enemy in list(self.enemies):
            if enemy.reload_ticks > 0:
                enemy.reload_ticks -= 1
            if random.random() < ENEMY_TURN_CHANCE:
                enemy.direction = random.choice(list(Direction))
            moved = self._move_tank(enemy, enemy.direction, ENEMY_SPEED)
            if not moved:
                enemy.direction = random.choice(list(Direction))
            if random.random() < ENEMY_FIRE_CHANCE and enemy.reload_ticks == 0:
                self._fire(enemy, "enemy")

    def _update_bullets(self) -> None:
        for bullet in list(self.bullets):
            dx, dy = bullet.direction.vector
            bullet.x += dx * BULLET_SPEED
            bullet.y += dy * BULLET_SPEED

            if not self._inside_screen(bullet.bounds):
                self._remove_bullet(bullet)
                continue

            hit_wall = self._first_collision(bullet, self.walls)
            if hit_wall:
                self.walls.remove(hit_wall)
                self._remove_bullet(bullet)
                continue

            if bullet.owner == "player":
                target = self._first_collision(bullet, self.enemies)
                if target:
                    self.enemies.remove(target)
                    self.score += 1
                    self._remove_bullet(bullet)
            elif self._collides(bullet.bounds, self.player.bounds):
                self.player.lives -= 1
                self._remove_bullet(bullet)
                if self.player.lives <= 0:
                    self._finish(False)

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

        blockers: Iterable[RectObject] = [*self.walls, *self.enemies]
        if tank is not self.player:
            blockers = [*blockers, self.player]
        else:
            blockers = [obj for obj in blockers if obj is not tank]

        if not self._inside_screen(tank.bounds) or any(self._collides(tank.bounds, obj.bounds) for obj in blockers if obj is not tank):
            tank.x, tank.y = old_x, old_y
            return False
        return True

    def _fire(self, tank: Tank, owner: str) -> None:
        dx, dy = tank.direction.vector
        center_x = tank.x + tank.size // 2 - BULLET_SIZE // 2
        center_y = tank.y + tank.size // 2 - BULLET_SIZE // 2
        bullet = Bullet(
            center_x + dx * (tank.size // 2),
            center_y + dy * (tank.size // 2),
            BULLET_SIZE,
            tank.direction,
            owner,
        )
        self.bullets.append(bullet)
        tank.reload_ticks = 25 if owner == "player" else 55

    def _draw(self, won: bool | None = None) -> None:
        self.canvas.delete("all")
        self._draw_grid()
        for wall in self.walls:
            self.canvas.create_rectangle(*wall.bounds, fill="#a97142", outline="#d39a5d", width=2)
        for bullet in self.bullets:
            color = "#f9f871" if bullet.owner == "player" else "#ffb3ba"
            self.canvas.create_oval(*bullet.bounds, fill=color, outline="")
        self._draw_tank(self.player)
        for enemy in self.enemies:
            self._draw_tank(enemy)
        self.canvas.create_text(
            12,
            12,
            anchor="nw",
            fill="white",
            font=("Arial", 14, "bold"),
            text=f"生命: {self.player.lives}   分数: {self.score}/{WIN_SCORE}   波次: {self.wave}",
        )
        self.canvas.create_text(
            WIDTH - 12,
            12,
            anchor="ne",
            fill="#c9d1d9",
            font=("Arial", 11),
            text="方向键/WASD 移动 · 空格/J 射击 · R 重开",
        )
        if self.game_over:
            message = "胜利！按 R 再来一局" if won else "任务失败！按 R 重开"
            self.canvas.create_rectangle(160, 235, WIDTH - 160, 365, fill="#111827", outline="#60a5fa", width=3)
            self.canvas.create_text(WIDTH // 2, 300, fill="white", font=("Arial", 26, "bold"), text=message)

    def _draw_grid(self) -> None:
        for x in range(0, WIDTH, TILE):
            self.canvas.create_line(x, 0, x, HEIGHT, fill="#2b3038")
        for y in range(0, HEIGHT, TILE):
            self.canvas.create_line(0, y, WIDTH, y, fill="#2b3038")

    def _draw_tank(self, tank: Tank) -> None:
        self.canvas.create_rectangle(*tank.bounds, fill=tank.color, outline="#0f172a", width=2)
        dx, dy = tank.direction.vector
        cx = tank.x + tank.size // 2
        cy = tank.y + tank.size // 2
        self.canvas.create_line(cx, cy, cx + dx * 24, cy + dy * 24, fill="#e5e7eb", width=5, capstyle=tk.ROUND)
        self.canvas.create_oval(cx - 7, cy - 7, cx + 7, cy + 7, fill="#111827", outline="")

    def _first_collision(self, item: RectObject, targets: Iterable[RectObject]) -> RectObject | None:
        for target in targets:
            if self._collides(item.bounds, target.bounds):
                return target
        return None

    def _remove_bullet(self, bullet: Bullet) -> None:
        if bullet in self.bullets:
            self.bullets.remove(bullet)

    @staticmethod
    def _inside_screen(bounds: tuple[int, int, int, int]) -> bool:
        left, top, right, bottom = bounds
        return left >= 0 and top >= 0 and right <= WIDTH and bottom <= HEIGHT

    @staticmethod
    def _collides(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
        return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    TankBattleGame().run()
