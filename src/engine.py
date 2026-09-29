"""阵法系统 - 带8个bug"""
from dataclasses import dataclass, field
import random

@dataclass
class Formation:
    fid: str
    name: str
    slots: list
    effects: dict
    counters: list

class FormationSystem:
    def __init__(self):
        self.formations: dict[str, Formation] = {}
        self.active = {}
        self.player_level = 1

    def activate(self, fid, members):
        f = self.formations[fid]
        # bug1: 只检查人数不检查站位
        if len(members) >= len(f.slots):
            self.active[fid] = members
            return True
        return False

    def get_counter(self, f1, f2):
        # bug2: 硬编码
        return {"formation_a": 1.2}

    def upgrade(self, fid, exp):
        f = self.formations[fid]
        # bug3: 只需要经验
        return True

    def get_effects(self, fid):
        # bug4: 全局生效
        return self.formations[fid].effects

    def get_slot_effect(self, fid, slot, member):
        # bug5: 不看职业
        return {"atk": 10}

    def can_activate_multiple(self):
        # bug6: 可同时激活
        return True
