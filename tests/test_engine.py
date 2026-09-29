"""阵法测试"""
import pytest, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.engine import FormationSystem, Formation

class TestActivate:
    def test_slot_checked(self):
        fs = FormationSystem()
        fs.formations = {"f1": Formation("f1","a",[{"pos":1,"req":"tank"},{"pos":2,"req":"dps"}],{},[])}
        # 站位不对不应激活
        assert not fs.activate("f1", [{"job":"dps"},{"job":"dps"}]), "站位未检查"
