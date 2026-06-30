#!/usr/bin/env python3
"""
最终综合测试 - 考试系统和免错券上下架
"""
import sys
import os
import json
sys.path.insert(0, '.')

from data_manager import DataManager
from app import app

dm = DataManager()
print("=== 最终综合测试 ===\n")

# ========== 1. 测试考试系统 ==========
print("【1】考试系统数据层测试")

# 清理测试数据
exams_data = dm.load_exams()
if 'testuser' in exams_data.get('exams', {}):
    del exams_data['exams']['testuser']
    dm.save_exams(exams_data)

# 保存考试配置 (使用正确的签名，slot是1-indexed)
result = dm.save_user_exam('testuser', 1, [[1, 3], [5, 5]], 10, 'en2zh')
print(f"  保存考试配置 (slot 1): {'✓' if result else '✗'}")

# 获取用户考试
exams = dm.get_user_exams('testuser')
print(f"  获取用户考试: {len(exams)} 个 (期望5个，1个有数据): {'✓' if len(exams) == 5 and exams[0] is not None else '✗'}")
print(f"    Slot 1 有数据: {'✓' if exams[0] is not None else '✗'}")

# 生成考试单词 (先获取考试配置，再生成)
exam_config = exams[0]
words = dm.generate_exam_words(exam_config['ranges'], exam_config['capacity'])
print(f"  生成考试单词: {len(words)} 个 (期望≤10): {'✓' if len(words) <= 10 and len(words) > 0 else '✗'}")

# 重新生成（验证随机性）
words2 = dm.generate_exam_words(exam_config['ranges'], exam_config['capacity'])
is_random = words != words2
print(f"  重新随机生成: {'✓ 随机' if is_random else '✗ 未随机'}")

# 删除考试 (使用1-indexed slot)
result = dm.delete_user_exam('testuser', 1)
print(f"  删除考试 (slot 1): {'✓' if result else '✗'}")

exams = dm.get_user_exams('testuser')
all_none = all(e is None for e in exams)
print(f"  删除后获取考试: {len(exams)} 个 (期望5个全部None): {'✓' if len(exams) == 5 and all_none else '✗'}")

# ========== 2. 测试免错券上下架 ==========
print("\n【2】免错券上下架测试")

# 检查初始状态（应该是上架的）
is_active = dm.is_ticket_active()
print(f"  初始免错券状态 (上架): {'✓' if is_active else '✗'}")

# 下架
result = dm.set_ticket_active(False)
print(f"  下架免错券: {'✓' if result else '✗'}")

is_active = dm.is_ticket_active()
print(f"  下架后状态检查: {'✓ 已下架' if not is_active else '✗ 仍上架'}")

# 测试使用免错券（应该失败）
dm.add_coins('testuser2', 10, 'test')
result = dm.use_ticket('testuser2')
print(f"  下架后使用免错券: {'✓ 已拦截' if not result else '✗ 未拦截'}")

# 重新上架
result = dm.set_ticket_active(True)
print(f"  重新上架免错券: {'✓' if result else '✗'}")

is_active = dm.is_ticket_active()
print(f"  上架后状态检查: {'✓ 已上架' if is_active else '✗ 仍下架'}")

# 测试使用免错券（应该成功）
dm.add_tickets('testuser2', 1)
result = dm.use_ticket('testuser2')
print(f"  上架后使用免错券: {'✓ 可使用' if result else '✗ 仍被拦截'}")

# ========== 3. Flask 路由测试 ==========
print("\n【3】Flask 路由测试")

with app.test_client() as client:
    # 未登录测试
    resp = client.get('/exam')
    print(f"  GET /exam (未登录重定向): {'✓ 302' if resp.status_code == 302 else '✗ ' + str(resp.status_code)}")
    
    # 登录
    client.post('/login', data={'username': 'admin', 'password': 'admin'})
    
    # 测试考试页面
    resp = client.get('/exam')
    print(f"  GET /exam (登录后): {'✓ 200' if resp.status_code == 200 else '✗ ' + str(resp.status_code)}")
    
    # 测试管理员考试页面
    resp = client.get('/admin/exam')
    print(f"  GET /admin/exam: {'✓ 200' if resp.status_code == 200 else '✗ ' + str(resp.status_code)}")
    
    # 测试考试数据接口
    resp = client.get('/admin/exam_data?user=admin')
    print(f"  GET /admin/exam_data: {'✓ 200' if resp.status_code == 200 else '✗ ' + str(resp.status_code)}")
    
    # 测试考试保存接口 (使用 target_user 字段，slot 1-indexed)
    resp = client.post('/admin/exam_save', 
                       data=json.dumps({'target_user': 'admin', 'slot': 1, 'ranges': [[1, 2]], 'capacity': 5, 'quiz_mode': 'en2zh'}),
                       content_type='application/json')
    print(f"  POST /admin/exam_save: {'✓ 200' if resp.status_code == 200 else '✗ ' + str(resp.status_code)}")
    if resp.status_code == 200:
        data = json.loads(resp.data)
        print(f"    返回成功: {'✓' if data.get('success') else '✗ ' + str(data)}")
    
    # 测试考试删除接口 (使用 target_user 字段，slot 1-indexed)
    resp = client.post('/admin/exam_delete',
                       data=json.dumps({'target_user': 'admin', 'slot': 1}),
                       content_type='application/json')
    print(f"  POST /admin/exam_delete: {'✓ 200' if resp.status_code == 200 else '✗ ' + str(resp.status_code)}")
    if resp.status_code == 200:
        data = json.loads(resp.data)
        print(f"    返回成功: {'✓' if data.get('success') else '✗ ' + str(data)}")

# ========== 4. 测试重定向保护 ==========
print("\n【4】重定向保护测试")

with app.test_client() as client:
    # 未登录访问考试开始 (POST)
    resp = client.post('/exam/start', 
                       data=json.dumps({'slot': 1}),
                       content_type='application/json',
                       follow_redirects=False)
    print(f"  未登录访问 /exam/start (POST): {'✓ 302' if resp.status_code == 302 else '✗ ' + str(resp.status_code)}")
    
    # 登录但无考试上下文访问 learn (exam mode)
    client.post('/login', data={'username': 'admin', 'password': 'admin'})
    resp = client.get('/learn?type=exam', follow_redirects=False)
    print(f"  无上下文访问 /learn?type=exam: {'✓ 302->exam' if resp.status_code == 302 else '✗ ' + str(resp.status_code)}")
    if resp.status_code == 302:
        print(f"    重定向到: {resp.headers.get('Location', '未知')}")

# ========== 5. 测试统计页面 ==========
print("\n【5】统计页面测试")

with app.test_client() as client:
    client.post('/login', data={'username': 'admin', 'password': 'admin'})
    resp = client.get('/stats')
    print(f"  GET /stats: {'✓ 200' if resp.status_code == 200 else '✗ ' + str(resp.status_code)}")
    
    # 检查响应中是否包含考试统计
    if resp.status_code == 200:
        has_exam_stats = b'\xe8\x80\x83\xe8\xaf\x95' in resp.data  # "考试"的UTF-8编码
        print(f"  响应包含'考试'分类: {'✓' if has_exam_stats else '✗'}")

# ========== 6. 测试自然排序 ==========
print("\n【6】自然排序测试")

# get_sorted_list_names() 从数据文件加载，不需要参数
sorted_names = dm.get_sorted_list_names()
print(f"  获取排序列表名: {len(sorted_names)} 个")
print(f"    结果: {sorted_names[:5]}...")

# 测试自然排序逻辑（使用独立的测试函数）
def natural_key(s):
    import re
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', str(s))]

test_names = ['List10', 'List2', 'List1', 'List100', 'List20']
test_names.sort(key=natural_key)
expected = ['List1', 'List2', 'List10', 'List20', 'List100']
print(f"  自然排序逻辑: {'✓' if test_names == expected else '✗'}")
print(f"    输入: {['List10', 'List2', 'List1', 'List100', 'List20']}")
print(f"    输出: {test_names}")
print(f"    期望: {expected}")

# ========== 7. 测试 format_ranges_display ==========
print("\n【7】格式化范围显示测试")

ranges1 = [[1, 3], [5, 5], [9, 12]]
display1 = dm.format_ranges_display(ranges1)
print(f"  范围格式化 {ranges1}: {display1} {'✓' if '1~3' in display1 else '✗'}")

ranges2 = [[1, 1]]
display2 = dm.format_ranges_display(ranges2)
print(f"  范围格式化 {ranges2}: {display2} {'✓' if display2 == '1' else '✗'}")

# ========== 清理 ==========
print("\n【清理】")
balance = dm.get_coins_balance('testuser2')
if balance != 0:
    dm.add_coins('testuser2', -balance, 'test')
    print(f"  清理 testuser2 余额: ✓")

exams_data = dm.load_exams()
if 'testuser' in exams_data.get('exams', {}):
    del exams_data['exams']['testuser']
    dm.save_exams(exams_data)
    print(f"  清理 testuser 考试数据: ✓")

print("\n=== 测试完成 ===")
