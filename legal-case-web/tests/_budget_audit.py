"""全面量化 build_questions 預算行為，找出真 Bug vs 預期 fail-closed。"""
import sys
sys.path.insert(0, '.')
from collections import Counter
from app.rules import load_bank, build_questions, MAX_OFFENSE_QUESTIONS, MAX_SELECTED_OFFENSES
from app.config import QUESTION_BANK_PATH
from app.rules import RuleError

bank = load_bank(QUESTION_BANK_PATH)

print(f"MAX_OFFENSE_QUESTIONS={MAX_OFFENSE_QUESTIONS}  MAX_SELECTED_OFFENSES={MAX_SELECTED_OFFENSES}")
print(f"offense count={len(bank['offenses'])}\n")

# 各罪章 offense_id 清單
all_ids = [o['id'] for o in bank['offenses']]

def run(role, offense_ids):
    """回傳 (ok, total, kinds, required, pruned, err)"""
    try:
        q = build_questions(bank, role, offense_ids)
        kinds = Counter(x.get('kind') for x in q)
        offense = [x for x in q if x.get('kind') not in ('company','common')]
        required = kinds.get('core',0) + kinds.get('company_offense',0)
        pruned = len(getattr(build_questions,'pruned_questions',[]) or [])
        return True, len(q), dict(kinds), len(offense), required, pruned, None
    except RuleError as e:
        return False, 0, {}, 0, 0, 0, str(e)

print("="*70)
print("【1】單一罪章 × 各角色 (theft, fraud, injury, sexual)")
print("="*70)
for role in ['victim','suspect','transfer']:
    for oid in ['theft','fraud','injury','sexual']:
        ok, total, kinds, off, req, pruned, err = run(role,[oid])
        if ok:
            print(f"  {role:9} + {oid:8} = {total:3} 題 (offense {off}, required {req}, pruned {pruned})")
        else:
            print(f"  {role:9} + {oid:8} = FAIL: {err[:50]}")

print()
print("="*70)
print("【2】3 罪章並列 × 各角色 (theft+fraud+injury)")
print("="*70)
for role in ['victim','suspect','transfer']:
    ok, total, kinds, off, req, pruned, err = run(role, ['theft','fraud','injury'])
    if ok:
        print(f"  {role:9} = {total:3} 題 (offense {off}, required {req}, pruned {pruned})")
    else:
        print(f"  {role:9} = FAIL: {err[:60]}")

print()
print("="*70)
print("【3】窮舉所有 3 罪章組合，統計各角色 fail 數量")
print("="*70)
import itertools
combinations = list(itertools.combinations(all_ids, 3))
for role in ['victim','suspect','transfer']:
    fails = 0
    total_required_max = 0
    for combo in combinations:
        ok, total, kinds, off, req, pruned, err = run(role, list(combo))
        if not ok:
            fails += 1
    print(f"  {role:9}: {fails}/{len(combinations)} 組合超載 fail")

print()
print("="*70)
print("【4】theft 單一罪章 calib（spec 註解宣稱 49 題→4頁）")
print("="*70)
for role in ['victim','suspect','transfer']:
    ok, total, kinds, off, req, pruned, err = run(role, ['theft'])
    print(f"  {role:9}: 實測 {total} 題 (spec 宣稱 theft=49)")
