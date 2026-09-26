import sys
sys.dont_write_bytecode = True
from pathlib import Path
R='/home/user/zhengzhibaodianzhizuo'
SK=R+'/.claude/skills/beijing-gaokao-politics/scripts'
sys.path.insert(0, SK)
import batch_health as bh, inspect
from profile_lib import load_profile
C=R+'/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925'
prof=load_profile(C+'/profiles_cloud/bixiu3.json')
print(inspect.signature(bh._unsafe_out))
docx=Path(R+'/必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx')
for out in [C+'/构建/入书_demo/09_health/bixiu3.json', C+'/构建/体检/x.json']:
    try:
        print(out.split('流程工具_20260925')[1], '->', bh._unsafe_out(Path(out), [docx], prof))
    except Exception as e:
        print('EXC', type(e).__name__, e)
