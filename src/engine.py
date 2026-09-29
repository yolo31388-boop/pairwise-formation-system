"""阵法系统"""
from dataclasses import dataclass, field

# ---------- 数据驱动配置(新增阵法/调整数值只改这里,不改逻辑) ----------

# 克制关系: COUNTER_TABLE[进攻方类型][防守方类型] = 伤害倍率
COUNTER_TABLE = {
    "attack": {"defense": 1.2},
    "defense": {"control": 1.2},
    "control": {"attack": 1.2},
}

# 站位职业适配: JOB_AFFINITY[站位要求][职业] = 加成系数
JOB_AFFINITY = {
    "tank": {"tank": 1.5, "warrior": 1.2},
    "dps": {"dps": 1.5, "assassin": 1.3},
    "dps_physical": {"warrior": 1.5, "assassin": 1.3},
    "dps_magic": {"mage": 1.5, "priest": 1.1},
    "heal": {"priest": 1.5},
}
MISMATCH_FACTOR = 0.5  # 职业不适配站位时的衰减系数

# 升级消耗: UPGRADE_COSTS[目标等级] = {exp, fragments}
UPGRADE_COSTS = {
    2: {"exp": 100, "fragments": 10},
    3: {"exp": 200, "fragments": 20},
    4: {"exp": 400, "fragments": 40},
    5: {"exp": 800, "fragments": 80},
}

# 突破要求: BREAKTHROUGHS[等级] = 额外需要的碎片, 突破后阶数+1
BREAKTHROUGHS = {
    3: {"fragments": 50},
}

# 技能触发概率: base + per_level * (level-1) + per_tier * (tier-1)
SKILL_CHANCE = {"base": 0.10, "per_level": 0.02, "per_tier": 0.05, "cap": 0.80}

RESET_COOLDOWN = 3600  # 重置冷却秒数, 冷却内需消耗重置道具


@dataclass
class Formation:
    fid: str
    name: str
    slots: list
    effects: dict
    counters: list
    ftype: str = ""      # 阵法类型, 同类型互斥
    level: int = 1
    tier: int = 1


class FormationSystem:
    def __init__(self, config=None):
        self.formations: dict[str, Formation] = {}
        self.active = {}
        self.equipped = set()
        self.player_level = 1
        self._last_reset = {}
        cfg = config or {}
        self.counters = cfg.get("counters", COUNTER_TABLE)
        self.affinity = cfg.get("affinity", JOB_AFFINITY)
        self.upgrade_costs = cfg.get("upgrade_costs", UPGRADE_COSTS)
        self.breakthroughs = cfg.get("breakthroughs", BREAKTHROUGHS)
        self.skill_chance = cfg.get("skill_chance", SKILL_CHANCE)
        self.reset_cooldown = cfg.get("reset_cooldown", RESET_COOLDOWN)

    # ---- 激活: 人数 + 每个站位有人且职业适配 ----
    def activate(self, fid, members):
        f = self.formations[fid]
        if len(members) < len(f.slots):
            return False
        for slot, member in zip(f.slots, members):
            if not member:
                return False
            if not self._compatible(slot.get("req"), member.get("job")):
                return False
        # 同类型互斥: 已有同类型阵法激活时拒绝
        for other_id in self.active:
            other = self.formations[other_id]
            if other_id != fid and f.ftype and other.ftype == f.ftype:
                return False
        self.active[fid] = members
        return True

    def _compatible(self, req, job):
        if req is None or job == req:
            return True
        return job in self.affinity.get(req, {})

    # ---- 克制: 数据驱动 ----
    def get_counter(self, f1, f2):
        t1 = self.formations[f1].ftype if isinstance(f1, str) else f1.ftype
        t2 = self.formations[f2].ftype if isinstance(f2, str) else f2.ftype
        return self.counters.get(t1, {}).get(t2, 1.0)

    # ---- 升级: 经验 + 碎片, 特定等级需突破 ----
    def upgrade(self, fid, exp, fragments=0):
        f = self.formations[fid]
        target = f.level + 1
        cost = self.upgrade_costs.get(target)
        if cost is None:
            return False
        if exp < cost["exp"] or fragments < cost["fragments"]:
            return False
        bt = self.breakthroughs.get(f.level)
        if bt and fragments < cost["fragments"] + bt["fragments"]:
            return False
        f.level = target
        if bt:
            f.tier += 1
        return True

    # ---- 属性: 仅装备中的阵法生效 ----
    def equip(self, fid):
        self.equipped.add(fid)

    def unequip(self, fid):
        self.equipped.discard(fid)

    def get_effects(self, fid):
        if fid not in self.equipped:
            return {}
        return self.formations[fid].effects

    # ---- 站位效果: 按职业适配, 空位无加成 ----
    def get_slot_effect(self, fid, slot, member):
        if not member:
            return {}
        mult = self._affinity_factor(slot.get("req"), member.get("job"))
        base = slot.get("effect") or self.formations[fid].effects
        return {k: v * mult for k, v in base.items()}

    def _affinity_factor(self, req, job):
        if req is None:
            return 1.0
        table = self.affinity.get(req, {})
        if job in table:
            return table[job]
        if job == req:
            return 1.0
        return MISMATCH_FACTOR

    # ---- 同类型互斥 ----
    def can_activate_multiple(self):
        return False

    # ---- 技能触发概率: 随等级和阶数提升 ----
    def get_skill_chance(self, fid):
        f = self.formations[fid]
        cfg = self.skill_chance
        chance = (cfg["base"]
                  + cfg["per_level"] * (f.level - 1)
                  + cfg["per_tier"] * (f.tier - 1))
        return min(cfg["cap"], chance)

    # ---- 重置: 冷却或消耗道具 ----
    def reset(self, fid, now=0, reset_stones=0):
        last = self._last_reset.get(fid)
        if reset_stones <= 0:
            if last is not None and now - last < self.reset_cooldown:
                return False
        f = self.formations[fid]
        f.level = 1
        f.tier = 1
        self._last_reset[fid] = now
        return True
