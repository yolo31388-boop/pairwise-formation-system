"""阵法系统"""
from dataclasses import dataclass, field
import time

# ---------- 数据驱动配置（新增阵法/调整数值只改配置，不改核心代码） ----------

# 克制关系表: (进攻阵法fid, 防守阵法fid) -> 伤害系数
COUNTER_CONFIG = {
    ("formation_a", "formation_b"): 1.2,
}
DEFAULT_COUNTER = 1.0

# 升级消耗
EXP_PER_LEVEL = 100          # 每级所需经验
FRAGMENTS_PER_LEVEL = 10     # 每级所需阵法碎片
BREAKTHROUGH_LEVELS = {5: 1, 10: 2}  # 升到该等级所需突破石数量

# 技能触发概率: base + level*per_level + tier*per_tier
BASE_SKILL_CHANCE = 0.10
SKILL_CHANCE_PER_LEVEL = 0.02
SKILL_CHANCE_PER_TIER = 0.05
MAX_SKILL_CHANCE = 0.95

# 重置冷却（秒），冷却内重置需消耗重置石
RESET_COOLDOWN = 3600

# 站位职业适配系数
JOB_MATCH_BONUS = 1.5       # 角色职业匹配站位要求
JOB_MISMATCH_PENALTY = 0.5  # 不匹配（如法师站物理位）


@dataclass
class Formation:
    fid: str
    name: str
    slots: list
    effects: dict
    counters: list
    ftype: str = "generic"  # 同类型阵法互斥


class FormationSystem:
    def __init__(self, counter_config=None):
        self.formations: dict[str, Formation] = {}
        self.active: dict[str, list] = {}      # fid -> [(slot, member)]
        self.equipped: set[str] = set()
        self.player_level = 1
        # 每个阵法的养成状态
        self.states: dict[str, dict] = {}
        self.inventory = {"reset_stone": 0, "breakthrough_stone": 0}
        # 克制关系数据驱动，可整体替换配置
        self.counter_config = COUNTER_CONFIG if counter_config is None else counter_config

    def _state(self, fid):
        return self.states.setdefault(
            fid, {"level": 1, "tier": 1, "last_reset": None}
        )

    # ---------- 激活：人数 + 站位双重检查 ----------

    def activate(self, fid, members):
        f = self.formations[fid]
        # 同类型阵法互斥：已有同类型阵法激活时拒绝
        for other_fid in self.active:
            if other_fid != fid and self.formations[other_fid].ftype == f.ftype:
                return False
        # 人数检查
        if len(members) < len(f.slots):
            return False
        # 站位检查：每个站位都必须有职业匹配的角色
        assigned = []
        used = set()
        for slot in f.slots:
            req = slot.get("req")
            match = None
            for i, m in enumerate(members):
                if i not in used and m is not None and m.get("job") == req:
                    match = (i, m)
                    break
            if match is None:
                return False  # 站位空缺或职业不符，不激活
            used.add(match[0])
            assigned.append((slot, match[1]))
        self.active[fid] = assigned
        return True

    # ---------- 克制：数据驱动 ----------

    def get_counter(self, f1, f2):
        return self.counter_config.get((f1, f2), DEFAULT_COUNTER)

    # ---------- 升级：经验 + 碎片 + 突破 ----------

    def upgrade(self, fid, exp=0, fragments=0, breakthrough_stones=0):
        state = self._state(fid)
        next_level = state["level"] + 1
        if exp < EXP_PER_LEVEL or fragments < FRAGMENTS_PER_LEVEL:
            return False
        need_stones = BREAKTHROUGH_LEVELS.get(next_level, 0)
        if breakthrough_stones < need_stones:
            return False
        state["level"] = next_level
        if need_stones:
            state["tier"] += 1  # 突破升阶
        return True

    # ---------- 属性：仅装备中的阵法生效 ----------

    def equip(self, fid):
        if fid in self.formations:
            self.equipped.add(fid)
            return True
        return False

    def unequip(self, fid):
        self.equipped.discard(fid)

    def get_effects(self, fid):
        if fid not in self.equipped:
            return {}  # 未装备只收集，不加属性
        f = self.formations[fid]
        effects = dict(f.effects)
        for slot, member in self.active.get(fid, []):
            for k, v in self.get_slot_effect(fid, slot, member).items():
                effects[k] = effects.get(k, 0) + v
        return effects

    # ---------- 站位效果：按职业适配 ----------

    def get_slot_effect(self, fid, slot, member):
        if member is None:
            return {}  # 空位不提供属性
        effect = dict(slot.get("effect", {"atk": 10}))
        scale = JOB_MATCH_BONUS if member.get("job") == slot.get("req") else JOB_MISMATCH_PENALTY
        return {k: v * scale for k, v in effect.items()}

    # ---------- 同类型互斥 ----------

    def can_activate_multiple(self):
        return False

    # ---------- 技能概率：随等级和阶数成长 ----------

    def get_skill_chance(self, fid):
        state = self._state(fid)
        chance = (BASE_SKILL_CHANCE
                  + SKILL_CHANCE_PER_LEVEL * (state["level"] - 1)
                  + SKILL_CHANCE_PER_TIER * (state["tier"] - 1))
        return min(chance, MAX_SKILL_CHANCE)

    # ---------- 重置：冷却或消耗道具 ----------

    def reset(self, fid, now=None):
        now = time.time() if now is None else now
        state = self._state(fid)
        last = state["last_reset"]
        on_cooldown = last is not None and now - last < RESET_COOLDOWN
        if on_cooldown:
            if self.inventory["reset_stone"] <= 0:
                return False  # 冷却中且无重置石，重置失败
            self.inventory["reset_stone"] -= 1
        self.active.pop(fid, None)
        state["last_reset"] = now
        return True
