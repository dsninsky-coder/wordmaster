from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from data_manager import DataManager
import random
import requests
import json
import re
import calendar
from datetime import datetime
from functools import wraps

VERSION = "0.2.0"

app = Flask(__name__)
app.secret_key = 'wordmaster-secret-key-2026'
dm = DataManager()

# 将 dm 和版本号注入模板全局，供 base.html 使用
@app.context_processor
def inject_globals():
    return dict(dm=dm, version=VERSION)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        if not dm.is_admin(session['user']):
            return redirect(url_for('study'))
        return f(*args, **kwargs)
    return decorated_function


# ---------- AI 判断辅助函数 ----------
def check_answer_with_ai(api_key, base_url, model, user_answer, word_en):
    """
    英中模式：判断用户输入的中文是否为英文单词的正确释义。
    """
    prompt = (
        f"请判断以下用户输入的中文是否为英文单词的正确释义。\n"
        f"用户输入：{user_answer}\n"
        f"英文单词：{word_en}\n"
        f"只回答'正确'或'错误'，不要解释。"
    )
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0
    }
    try:
        url = base_url.rstrip('/') + "/chat/completions"
        print(f"[AI DEBUG] 模型={model}, URL={url}")
        print(f"[AI DEBUG] 发送: user_answer={user_answer}, word_en={word_en}")
        print(f"[AI DEBUG] API Key={api_key[:10]}...{api_key[-4:]}")
        response = requests.post(url, headers=headers, json=data, timeout=8)
        print(f"[AI DEBUG] HTTP={response.status_code}, 响应={response.text[:300]}")
        result = response.json()["choices"][0]["message"]["content"].strip()
        print(f"[AI DEBUG] AI回答={result}, 判定={'正确' if '正确' in result else '错误'}")
        return "正确" in result
    except Exception as e:
        print(f"[AI DEBUG] 异常: {type(e).__name__}: {e}")
        return None


def check_answer_keyword(user_answer, expected_meaning):
    user_chars = set(re.findall(r'[\u4e00-\u9fff]', user_answer))
    expected_chars = set(re.findall(r'[\u4e00-\u9fff]', expected_meaning))
    if not user_chars:
        return False
    overlap = user_chars & expected_chars
    return len(overlap) >= max(1, len(user_chars) * 0.7)


def judge_en2zh(user_answer, word_zh, word_en, config):
    """
    英中判定逻辑：
    1. 精确匹配 → 直接正确
    2. 本地关键词算法 → 正确则不再调 AI
    3. 本地判定错误 → AI 二次判定（以 AI 为准）
    """
    user_answer = user_answer.strip()
    if not user_answer:
        return False, "fallback"
    if user_answer == word_zh:
        return True, "exact"

    # 先本地关键词判定
    local_result = check_answer_keyword(user_answer, word_zh)
    if local_result:
        # 本地判定正确，直接通过，不调 AI
        return True, "keyword"

    # 本地判定错误，用 AI 二次判定
    if config.get('chatgpt_api_key'):
        print(f"[JUDGE en2zh] 本地判定错误，启用AI二次判定: answer={user_answer}, word={word_en}")
        ai_result = check_answer_with_ai(
            config['chatgpt_api_key'],
            config.get('chatgpt_base_url', 'https://api.openai.com/v1'),
            config.get('ai_model', 'deepseek-chat'),
            user_answer, word_en
        )
        if ai_result is not None:
            return ai_result, "ai"

    # AI 不可用或调用失败，以本地判定为准（错误）
    return False, "keyword"


def judge_zh2en(user_answer, word_en):
    """中英模式：只做精确匹配（字母数量确定，无误差空间）"""
    user_answer = user_answer.strip()
    if not user_answer:
        return False, "fallback"
    return user_answer.lower() == word_en.lower(), "exact"


# ---------- 首页路由 ----------
@app.route('/')
def index():
    if 'user' in session:
        if dm.is_admin(session['user']):
            return redirect(url_for('coins'))
        return redirect(url_for('study'))
    return redirect(url_for('login'))


# ---------- 登录/注册 ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if dm.verify_user(username, password):
            session['user'] = username
            # 标记今日已登录（用于金币页面手动领取判断）
            dm.mark_checkin(username, 'login_visited')
            if dm.is_admin(username):
                return redirect(url_for('coins'))
            return redirect(url_for('study'))
        else:
            return render_template('login.html', error='用户名或密码错误')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        if password != confirm:
            return render_template('register.html', error='两次密码不一致')
        success, msg = dm.register_user(username, password)
        if success:
            session['user'] = username
            return redirect(url_for('study'))
        else:
            return render_template('register.html', error=msg)
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('study_context', None)
    session.pop('review_context', None)
    return redirect(url_for('login'))


# ---------- 新背单词 ----------
@app.route('/study', methods=['GET'])
@login_required
def study():
    words = dm.load_words()
    list_word_count = dm.get_list_word_count()
    history = dm.load_user_history(session['user'])
    learned_lists = history.get("learned_lists", [])
    config, _ = dm.get_effective_config(session['user'])
    review_count = dm.get_review_count(session['user'])

    must_review = False
    review_mode = config.get('review_mode', 'none')
    # 向后兼容旧的 require_review_before_study 字段
    if review_mode == 'none' and config.get('require_review_before_study', False):
        review_mode = 'all'

    if review_mode == 'all' and review_count > 0:
        must_review = True
    elif review_mode == 'once' and review_count > 0:
        # once 模式：今天已经通过过一次则不强制
        if not dm.is_review_once_cleared(session['user']):
            must_review = True

    # 计算冷却剩余时间
    cooldowns = {}
    for list_name in words.keys():
        remaining = dm.get_list_cooldown_remaining(session['user'], list_name)
        if remaining > 0:
            cooldowns[list_name] = remaining

    # 每个词单最后一次 study 模式的成绩（percent, passed）
    quiz_results = history.get("quiz_results", [])
    last_study_result = {}  # { list_name: {"percent": float, "passed": bool} }
    for r in quiz_results:
        if r.get("mode") == "study":
            last_study_result[r["list"]] = {
                "percent": r.get("percent", 0),
                "passed": r.get("passed", False)
            }

    return render_template(
        'study.html',
        lists=list(words.keys()),
        list_word_count=list_word_count,
        learned_lists=learned_lists,
        must_review=must_review,
        review_count=review_count,
        review_mode=review_mode,
        cooldowns=cooldowns,
        last_study_result=last_study_result
    )


@app.route('/study/preview', methods=['POST'])
@login_required
def study_preview():
    data = request.get_json()
    list_name = data.get('list_name')
    words = dm.load_words()
    if list_name not in words:
        return jsonify({'success': False, 'error': '列表不存在'})
    word_list = words[list_name]
    preview = [{'word': w['word'], 'meaning': w['meaning']} for w in word_list]
    return jsonify({'success': True, 'preview': preview, 'list_name': list_name, 'total': len(preview)})


@app.route('/study/start', methods=['POST'])
@login_required
def study_start():
    data = request.get_json()
    list_name = data.get('list_name')
    is_rechallenge = data.get('is_rechallenge', False)

    # 检查冷却
    remaining = dm.get_list_cooldown_remaining(session['user'], list_name)
    if remaining > 0:
        return jsonify({'success': False, 'error': f'还需等待 {remaining} 秒后才能再次答题', 'cooldown': remaining})

    # "新学前必须复习"检查：仅"开始学习"受限制，"重新挑战"不受影响
    if not is_rechallenge:
        config, _ = dm.get_effective_config(session['user'])
        review_mode = config.get('review_mode', 'none')
        # 向后兼容
        if review_mode == 'none' and config.get('require_review_before_study', False):
            review_mode = 'all'

        need_review = False
        if review_mode == 'all':
            review_count = dm.get_review_count(session['user'])
            if review_count > 0:
                need_review = True
        elif review_mode == 'once':
            review_count = dm.get_review_count(session['user'])
            if review_count > 0 and not dm.is_review_once_cleared(session['user']):
                need_review = True

        if need_review:
            return jsonify({
                'success': False,
                'need_review': True,
                'review_count': review_count,
                'error': f'你有 {review_count} 个单词待复习，请先完成复习再开始新背'
            })

    words = dm.load_words()
    if list_name not in words:
        return jsonify({'success': False, 'error': '列表不存在'})
    word_list = words[list_name][:]
    random.shuffle(word_list)
    session['study_context'] = {
        'mode': 'study',
        'list_name': list_name,
        'words': word_list,
        'current_index': 0,
        'correct_count': 0,
        'total': len(word_list),
        'wrong_words': [],
        'quiz_mode': 'en2zh'   # 当前答题方向
    }
    return jsonify({'success': True})


@app.route('/study/next', methods=['GET'])
@login_required
def study_next():
    ctx = session.get('study_context')
    if not ctx or ctx['mode'] != 'study':
        return jsonify({'error': '无进行中的学习'}), 400
    if ctx['current_index'] >= ctx['total']:
        list_name = ctx['list_name']
        correct = ctx['correct_count']
        total = ctx['total']
        quiz_mode = ctx.get('quiz_mode', 'en2zh')
        passed = (correct / total >= 0.8) if total > 0 else False

        dm.add_learned_list(session['user'], list_name)
        dm.add_quiz_result(session['user'], list_name, correct, total, mode="study", quiz_mode=quiz_mode)

        if not passed:
            # 未通过：设置冷却
            admin_cfg = dm.load_admin_config()
            cooldown = admin_cfg.get('retry_cooldown_seconds', 60)
            dm.set_list_cooldown(session['user'], list_name, cooldown)

        session.pop('study_context', None)

        # 打卡金币：新背通过 → +3金币（每日首次通过）
        coin_grant = None
        if passed:
            granted, new_bal = dm.try_grant_checkin(
                session['user'], 'study', 3, f'每日打卡-新背通过 ({list_name})')
            if granted:
                coin_grant = {'coins': 3, 'new_balance': new_bal,
                              'reason': '新背通过获得 +3 金币！'}

        return jsonify({
            'finished': True,
            'passed': passed,
            'message': f'完成 {list_name} 学习！',
            'correct': correct,
            'total': total,
            'percent': round(correct / total * 100, 1) if total > 0 else 0,
            'list_name': list_name,
            'coin_grant': coin_grant
        })
    word = ctx['words'][ctx['current_index']]
    return jsonify({
        'finished': False,
        'word': word,
        'index': ctx['current_index'] + 1,
        'total': ctx['total']
    })


@app.route('/study/submit', methods=['POST'])
@login_required
def study_submit():
    ctx = session.get('study_context')
    if not ctx or ctx['mode'] != 'study':
        return jsonify({'error': '无进行中的学习'}), 400
    data = request.get_json()
    mode = data.get('mode', 'en2zh')
    user_answer = data.get('answer', '').strip()
    word = ctx['words'][ctx['current_index']]
    word_en = word['word']
    word_zh = word['meaning']
    config, _ = dm.get_effective_config(session['user'])

    # 更新当前 quiz_mode
    ctx['quiz_mode'] = mode
    session['study_context'] = ctx

    if mode == 'en2zh' or mode == 'audio2zh':
        correct, method = judge_en2zh(user_answer, word_zh, word_en, config)
    else:
        correct, method = judge_zh2en(user_answer, word_en)

    dm.update_word_review(session['user'], ctx['list_name'], word_en, correct)

    if correct:
        ctx['correct_count'] += 1
        ctx['current_index'] += 1
        session['study_context'] = ctx
        return jsonify({'correct': True, 'message': '✓ 回答正确！', 'method': method})
    else:
        # 答错：不推进 index，返回正确答案，等待前端点"下一题"后再推进
        ctx.setdefault('wrong_words', [])
        if word_en not in ctx['wrong_words']:
            ctx['wrong_words'].append(word_en)
        session['study_context'] = ctx
        return jsonify({
            'correct': False,
            'expected': word_en if mode == 'zh2en' else word_zh,
            'message': '✗ 回答错误',
            'method': method,
            'need_advance': True   # 告知前端需要手动推进
        })


@app.route('/study/advance', methods=['POST'])
@login_required
def study_advance():
    """答错后手动推进到下一题"""
    ctx = session.get('study_context')
    if not ctx or ctx['mode'] != 'study':
        return jsonify({'error': '无进行中的学习'}), 400
    ctx['current_index'] += 1
    session['study_context'] = ctx
    return jsonify({'success': True})


@app.route('/study/restart', methods=['POST'])
@login_required
def study_restart():
    """切换答题模式：保留词单，重置进度，切换quiz_mode"""
    ctx = session.get('study_context')
    if not ctx or ctx['mode'] != 'study':
        return jsonify({'error': '无进行中的学习'}), 400
    data = request.get_json() or {}
    new_mode = data.get('mode', 'en2zh')
    if new_mode not in ('en2zh', 'zh2en', 'audio2zh'):
        new_mode = 'en2zh'
    # 保留词单，重新打乱，重置进度
    random.shuffle(ctx['words'])
    ctx['quiz_mode'] = new_mode
    ctx['current_index'] = 0
    ctx['correct_count'] = 0
    session['study_context'] = ctx
    return jsonify({'success': True})


# ---------- 复习 ----------
@app.route('/review')
@login_required
def review():
    config, controlled_fields = dm.get_effective_config(session['user'])
    review_count = dm.get_review_count(session['user'])
    review_cooldown = dm.get_list_cooldown_remaining(session['user'], 'review')
    return render_template(
        'review.html',
        review_count=review_count,
        default_limit=config.get('review_count', 20),
        review_cooldown=review_cooldown,
        review_count_controlled='review_count' in controlled_fields
    )


@app.route('/review/start', methods=['POST'])
@login_required
def review_start():
    # 检查冷却
    remaining = dm.get_list_cooldown_remaining(session['user'], 'review')
    if remaining > 0:
        return jsonify({'success': False, 'message': f'复习未通过，还需等待 {remaining} 秒后才能再次复习', 'cooldown': remaining})

    data = request.get_json()
    config, _ = dm.get_effective_config(session['user'])
    limit = data.get('limit', config.get('review_count', 20))
    review_words = dm.get_review_words(session['user'], limit)
    if not review_words:
        return jsonify({'success': False, 'message': '当前没有需要复习的单词 🎉'})
    shuffled = review_words[:]
    random.shuffle(shuffled)
    session['review_context'] = {
        'mode': 'review',
        'words': shuffled,
        'current_index': 0,
        'correct_count': 0,
        'total': len(shuffled),
        'wrong_words': [],
        'quiz_mode': 'en2zh'
    }
    return jsonify({'success': True, 'total': len(shuffled)})


@app.route('/review/next', methods=['GET'])
@login_required
def review_next():
    ctx = session.get('review_context')
    if not ctx or ctx['mode'] != 'review':
        return jsonify({'error': '无进行中的复习'}), 400
    if ctx['current_index'] >= ctx['total']:
        correct = ctx['correct_count']
        total = ctx['total']
        correct_rate = correct / total if total > 0 else 0
        passed = correct_rate >= 0.8
        quiz_mode = ctx.get('quiz_mode', 'en2zh')
        wrong_words = ctx.get('wrong_words', [])
        dm.add_quiz_result(session['user'], 'review', correct, total, mode="review", quiz_mode=quiz_mode)

        if not passed:
            # 未通过：设置冷却时间（限制立即重试）
            admin_cfg = dm.load_admin_config()
            cooldown = admin_cfg.get('retry_cooldown_seconds', 60)
            dm.set_list_cooldown(session['user'], 'review', cooldown)
        else:
            # 通过：若当前是 once 模式，记录今日已完成
            config, _ = dm.get_effective_config(session['user'])
            if config.get('review_mode', 'none') == 'once':
                dm.set_review_once_cleared(session['user'])

        session.pop('review_context', None)

        # 本轮结束后，待复习池中仍剩余的单词数（包括答错的+未被抽到的）
        remaining_count = dm.get_review_count(session['user'])

        # 打卡金币：复习通过 → +5金币（每日首次通过）
        coin_grant = None
        if passed:
            granted, new_bal = dm.try_grant_checkin(
                session['user'], 'review', 5, '每日打卡-复习任务通过')
            if granted:
                coin_grant = {'coins': 5, 'new_balance': new_bal,
                              'reason': '复习通过获得 +5 金币！'}

        return jsonify({
            'finished': True,
            'passed': passed,
            'correct': correct,
            'total': total,
            'percent': round(correct_rate * 100, 1),
            'wrong_count': len(wrong_words),
            'remaining_review': remaining_count,
            'coin_grant': coin_grant,
            'message': f'复习{"通过" if passed else "未通过"}！正确率 {correct_rate*100:.1f}%'
        })
    word = ctx['words'][ctx['current_index']]
    return jsonify({
        'finished': False,
        'word': word,
        'index': ctx['current_index'] + 1,
        'total': ctx['total']
    })


@app.route('/review/submit', methods=['POST'])
@login_required
def review_submit():
    ctx = session.get('review_context')
    if not ctx or ctx['mode'] != 'review':
        return jsonify({'error': '无进行中的复习'}), 400
    data = request.get_json()
    mode = data.get('mode', 'en2zh')
    user_answer = data.get('answer', '').strip()
    word = ctx['words'][ctx['current_index']]
    word_en = word['word']
    word_zh = word['meaning']
    config, _ = dm.get_effective_config(session['user'])

    ctx['quiz_mode'] = mode
    session['review_context'] = ctx

    if mode == 'en2zh' or mode == 'audio2zh':
        correct, method = judge_en2zh(user_answer, word_zh, word_en, config)
    else:
        correct, method = judge_zh2en(user_answer, word_en)

    dm.update_word_review(session['user'], word['list'], word_en, correct)

    if correct:
        ctx['correct_count'] += 1
        ctx['current_index'] += 1
        session['review_context'] = ctx
        return jsonify({'correct': True, 'message': '✓ 回答正确！', 'method': method})
    else:
        ctx.setdefault('wrong_words', [])
        if word_en not in ctx['wrong_words']:
            ctx['wrong_words'].append(word_en)
        session['review_context'] = ctx
        return jsonify({
            'correct': False,
            'expected': word_en if mode == 'zh2en' else word_zh,
            'message': '✗ 回答错误',
            'method': method,
            'need_advance': True
        })


@app.route('/review/advance', methods=['POST'])
@login_required
def review_advance():
    """答错后手动推进到下一题"""
    ctx = session.get('review_context')
    if not ctx or ctx['mode'] != 'review':
        return jsonify({'error': '无进行中的复习'}), 400
    ctx['current_index'] += 1
    session['review_context'] = ctx
    return jsonify({'success': True})


@app.route('/review/restart', methods=['POST'])
@login_required
def review_restart():
    """切换答题模式：保留词单，重置进度，切换quiz_mode"""
    ctx = session.get('review_context')
    if not ctx or ctx['mode'] != 'review':
        return jsonify({'error': '无进行中的复习'}), 400
    data = request.get_json() or {}
    new_mode = data.get('mode', 'en2zh')
    if new_mode not in ('en2zh', 'zh2en', 'audio2zh'):
        new_mode = 'en2zh'
    random.shuffle(ctx['words'])
    ctx['quiz_mode'] = new_mode
    ctx['current_index'] = 0
    ctx['correct_count'] = 0
    session['review_context'] = ctx
    return jsonify({'success': True})


# ---------- 单词导入 ----------
@app.route('/import', methods=['GET'])
@login_required
def import_words():
    list_info = dm.get_list_word_count()
    return render_template('import.html', list_info=list_info)


@app.route('/import/upload', methods=['POST'])
@login_required
def import_upload():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '未选择文件'})
    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'error': '未选择文件'})

    filename = file.filename.lower()
    content = file.read()

    try:
        if filename.endswith('.csv'):
            rows = dm.parse_csv_content(content)
        elif filename.endswith('.txt'):
            rows = dm.parse_txt_content(content)
        else:
            return jsonify({'success': False, 'error': '只支持 CSV 或 TXT 文件'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'文件解析失败：{str(e)}'})

    if not rows:
        return jsonify({'success': False, 'error': '未解析到有效数据，请检查文件格式'})

    preview = rows[:50]
    return jsonify({
        'success': True,
        'total': len(rows),
        'preview': preview,
        'rows_json': json.dumps(rows)
    })


@app.route('/import/confirm', methods=['POST'])
@login_required
def import_confirm():
    data = request.get_json()
    rows_json = data.get('rows_json', '[]')
    overwrite = data.get('overwrite', False)
    try:
        rows = json.loads(rows_json)
    except Exception:
        return jsonify({'success': False, 'error': '数据格式错误'})

    imported, skipped, list_names = dm.import_words_from_data(rows, overwrite=overwrite)
    return jsonify({
        'success': True,
        'imported': imported,
        'skipped': skipped,
        'list_names': list_names,
        'message': f'成功导入 {imported} 个单词，跳过 {skipped} 个'
    })


# ---------- 用户设置 ----------
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    username = session['user']
    config, controlled_fields = dm.get_effective_config(username)
    msg = None

    if request.method == 'POST':
        action = request.form.get('action', 'save_config')
        if action == 'save_config':
            user_history = dm.load_user_history(username)
            prefs = user_history.get("user_prefs", {})

            # 只更新未被管控的字段
            if 'review_count' not in controlled_fields:
                try:
                    prefs['review_count'] = int(request.form.get('review_count', 20))
                except ValueError:
                    prefs['review_count'] = 20

            if 'chatgpt_api_key' not in controlled_fields:
                prefs['chatgpt_api_key'] = request.form.get('api_key', '').strip()
                prefs['chatgpt_base_url'] = request.form.get('base_url', 'https://api.openai.com/v1').strip()
                prefs['ai_model'] = request.form.get('ai_model', 'deepseek-chat').strip()

            if 'require_review_before_study' not in controlled_fields:
                prefs['require_review_before_study'] = 'require_review' in request.form

            if 'require_both_modes' not in controlled_fields:
                prefs['require_both_modes'] = 'require_both_modes' in request.form

            dm.save_user_prefs(username, prefs)
            # 刷新
            config, controlled_fields = dm.get_effective_config(username)
            msg = ('success', '设置已保存！')

        elif action == 'change_password':
            old_pwd = request.form.get('old_password', '')
            new_pwd = request.form.get('new_password', '')
            confirm_pwd = request.form.get('confirm_password', '')
            if new_pwd != confirm_pwd:
                msg = ('error', '两次新密码不一致')
            else:
                success, text = dm.change_password(username, old_pwd, new_pwd)
                msg = ('success' if success else 'error', text)

    is_api_controlled = 'chatgpt_api_key' in controlled_fields
    return render_template(
        'settings.html',
        config=config,
        controlled_fields=controlled_fields,
        is_api_controlled=is_api_controlled,
        msg=msg
    )


# ---------- 超级管理员 ----------
@app.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin():
    admin_cfg = dm.load_admin_config()
    all_users = dm.get_all_usernames()
    msg = None

    if request.method == 'POST':
        action = request.form.get('action', '')

        if action == 'save_api':
            admin_cfg['shared_api_key'] = request.form.get('shared_api_key', '').strip()
            admin_cfg['shared_base_url'] = request.form.get('shared_base_url', 'https://api.openai.com/v1').strip()
            admin_cfg['shared_ai_model'] = request.form.get('shared_ai_model', 'deepseek-chat').strip()
            admin_cfg['retry_cooldown_seconds'] = int(request.form.get('retry_cooldown_seconds', 60))
            # 音译汉 & 英译汉发音设置
            admin_cfg['tts_in_en2zh'] = 'tts_in_en2zh' in request.form
            admin_cfg['audio2zh_enabled'] = 'audio2zh_enabled' in request.form
            # 允许使用共享API的用户
            allowed = request.form.getlist('allowed_api_users')
            admin_cfg['allowed_api_users'] = allowed
            dm.save_admin_config(admin_cfg)
            msg = ('success', 'API 设置已保存！')

        elif action == 'save_user_control':
            target_user = request.form.get('target_user', '')
            if target_user in all_users:
                # 构建管控字段
                controlled = {}
                field_enable = request.form.getlist('control_fields')

                if 'review_count' in field_enable:
                    try:
                        controlled['review_count'] = int(request.form.get('ctrl_review_count', 20))
                    except ValueError:
                        controlled['review_count'] = 20

                if 'require_review_before_study' in field_enable:
                    controlled['require_review_before_study'] = 'ctrl_require_review' in request.form

                if 'review_mode' in field_enable:
                    controlled['review_mode'] = request.form.get('ctrl_review_mode', 'none')

                if 'require_both_modes' in field_enable:
                    controlled['require_both_modes'] = 'ctrl_require_both_modes' in request.form

                # 更新
                if not admin_cfg.get('controlled_users'):
                    admin_cfg['controlled_users'] = {}
                admin_cfg['controlled_users'][target_user] = controlled
                dm.save_admin_config(admin_cfg)
                msg = ('success', f'已对用户 {target_user} 应用管控设置！')

        elif action == 'remove_user_control':
            target_user = request.form.get('target_user', '')
            if target_user in admin_cfg.get('controlled_users', {}):
                del admin_cfg['controlled_users'][target_user]
                dm.save_admin_config(admin_cfg)
                msg = ('success', f'已取消对用户 {target_user} 的管控！')

        elif action == 'reset_user_password':
            target_user = request.form.get('target_user', '').strip()
            new_pwd = request.form.get('new_password', '')
            confirm_pwd = request.form.get('confirm_password', '')
            if not target_user or target_user not in all_users:
                msg = ('error', '目标用户不存在')
            elif new_pwd != confirm_pwd:
                msg = ('error', '两次输入的新密码不一致')
            else:
                success, text = dm.admin_reset_password(target_user, new_pwd)
                msg = ('success' if success else 'error', text)

    # 刷新
    admin_cfg = dm.load_admin_config()
    all_users = dm.get_all_usernames()
    all_users_all = dm.get_all_usernames_with_admin()
    return render_template(
        'admin.html',
        admin_cfg=admin_cfg,
        all_users=all_users,
        all_users_all=all_users_all,
        msg=msg
    )


@app.route('/admin/user_control_data', methods=['GET'])
@admin_required
def admin_user_control_data():
    """获取指定用户当前管控设置（AJAX）"""
    target_user = request.args.get('user', '')
    admin_cfg = dm.load_admin_config()
    controlled = admin_cfg.get('controlled_users', {}).get(target_user, {})
    config, _ = dm.get_effective_config(target_user)
    return jsonify({
        'controlled': controlled,
        'effective_config': config
    })

@app.route('/admin/grant_coins', methods=['POST'])
@admin_required
def admin_grant_coins():
    """管理员发放金币给用户（需验证管理员密码）"""
    admin_user = session['user']
    data = request.get_json()
    target_user = data.get('target_user', '').strip()
    amount = int(data.get('amount', 0))
    message = data.get('message', '').strip()
    admin_password = data.get('admin_password', '')

    # 验证管理员密码
    if not dm.verify_user(admin_user, admin_password):
        return jsonify({'success': False, 'message': '管理员密码错误'})

    # 校验目标用户
    all_users = dm.get_all_usernames_with_admin()
    if not target_user or target_user not in all_users:
        return jsonify({'success': False, 'message': '目标用户不存在'})

    if amount == 0:
        return jsonify({'success': False, 'message': '金币数量不能为 0'})

    # 组装流水备注
    reason = f'管理员 {admin_user} 发放：{message}' if message else f'管理员 {admin_user} 发放'
    new_bal = dm.add_coins(target_user, amount, reason)
    if new_bal is False:
        return jsonify({'success': False, 'message': '操作失败，用户金币余额不足（扣款时）'})

    return jsonify({
        'success': True,
        'new_balance': new_bal,
        'message': f'成功向 {target_user} {"发放" if amount > 0 else "扣除"} {abs(amount)} 金币！'
    })


# ---------- 统计 ----------
@app.route('/stats')
@login_required
def stats():
    username = session['user']

    # 管理员可以查看指定用户的统计
    view_user = request.args.get('user', '').strip()
    if view_user and dm.is_admin(username) and view_user != username:
        # 验证目标用户存在
        if view_user not in dm.get_all_usernames():
            return redirect(url_for('stats'))
        target_user = view_user
        is_viewing_other = True
    else:
        target_user = username
        is_viewing_other = False
    history = dm.load_user_history(target_user)
    daily_status = dm.get_daily_status(target_user)

    now = datetime.now()
    try:
        year = int(request.args.get('year', now.year))
        month = int(request.args.get('month', now.month))
    except ValueError:
        year, month = now.year, now.month

    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    days_in_month = calendar.monthrange(year, month)[1]
    first_weekday = calendar.weekday(year, month, 1)

    cal = []
    week = [''] * first_weekday
    for d in range(1, days_in_month + 1):
        week.append(d)
        if len(week) == 7:
            cal.append(week)
            week = []
    if week:
        while len(week) < 7:
            week.append('')
        cal.append(week)

    quiz_results = history.get('quiz_results', [])

    # 分模式统计
    en2zh_results = [r for r in quiz_results if r.get('quiz_mode', 'en2zh') == 'en2zh']
    zh2en_results = [r for r in quiz_results if r.get('quiz_mode', 'en2zh') == 'zh2en']
    audio2zh_results = [r for r in quiz_results if r.get('quiz_mode', 'en2zh') == 'audio2zh']

    def calc_stats(results):
        total_q = len(results)
        total_w = sum(r.get('total', 0) for r in results)
        total_c = sum(r.get('correct', 0) for r in results)
        avg_p = round(total_c / total_w * 100, 1) if total_w > 0 else 0
        return {'count': total_q, 'words': total_w, 'correct': total_c, 'avg_percent': avg_p}

    total_quizzes = len(quiz_results)
    total_words = sum(r.get('total', 0) for r in quiz_results)
    total_correct = sum(r.get('correct', 0) for r in quiz_results)
    avg_percent = round(total_correct / total_words * 100, 1) if total_words > 0 else 0
    learned_lists = history.get('learned_lists', [])

    return render_template(
        'stats.html',
        history=history,
        daily_status=daily_status,
        year=year,
        month=month,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        calendar_cells=cal,
        total_quizzes=total_quizzes,
        total_words=total_words,
        avg_percent=avg_percent,
        learned_lists=learned_lists,
        en2zh_stats=calc_stats(en2zh_results),
        zh2en_stats=calc_stats(zh2en_results),
        audio2zh_stats=calc_stats(audio2zh_results),
        view_user=target_user if is_viewing_other else None,
        all_users=dm.get_all_usernames() if dm.is_admin(username) else []
    )


# ---------- 学习/复习统一界面 ----------
@app.route('/learn')
@login_required
def learn():
    quiz_type = request.args.get('type', 'study')
    if quiz_type not in ['study', 'review']:
        return redirect(url_for('coins'))
    quiz_mode = request.args.get('mode', 'en2zh')
    if quiz_mode not in ['en2zh', 'zh2en', 'audio2zh']:
        quiz_mode = 'en2zh'
    admin_cfg = dm.load_admin_config()
    tts_in_en2zh = admin_cfg.get('tts_in_en2zh', False)
    audio2zh_enabled = admin_cfg.get('audio2zh_enabled', True)
    return render_template('check.html', type=quiz_type, mode=quiz_mode,
                           tts_in_en2zh=tts_in_en2zh, audio2zh_enabled=audio2zh_enabled)


# ============================================================
# 金币 / 打卡
# ============================================================
@app.route('/coins')
@login_required
def coins():
    username = session['user']
    balance = dm.get_coins_balance(username)
    ledger = dm.get_coins_ledger(username, limit=50)
    checkin_done = dm.get_checkin_status(username)
    ticket_count = dm.get_ticket_count(username)
    return render_template('coins.html',
                           balance=balance,
                           ledger=ledger,
                           checkin_done=checkin_done,
                           ticket_count=ticket_count)


@app.route('/coins/checkin_login', methods=['POST'])
@login_required
def coins_checkin_login():
    """首页手动领取每日登录金币"""
    username = session['user']
    # 必须当日已登录才能领取
    done = dm.get_checkin_status(username)
    if 'login_visited' not in done:
        return jsonify({'success': False, 'message': '请先登录后再领取'})
    granted, new_bal = dm.try_grant_checkin(username, 'login', 1, '每日首次登录签到')
    if granted:
        return jsonify({'success': True, 'coins': 1, 'new_balance': new_bal,
                        'message': '成功领取登录奖励 +1 金币！'})
    return jsonify({'success': False, 'message': '今日登录奖励已领取'})


@app.route('/coins/balance', methods=['GET'])
@login_required
def coins_balance():
    return jsonify({'balance': dm.get_coins_balance(session['user'])})


# ============================================================
# 商城
# ============================================================
@app.route('/shop')
@login_required
def shop():
    username = session['user']
    products = dm.get_products(active_only=True)
    my_orders = dm.get_orders(username=username)
    balance = dm.get_coins_balance(username)
    ticket_count = dm.get_ticket_count(username)
    return render_template('shop.html',
                           products=products,
                           my_orders=my_orders,
                           balance=balance,
                           ticket_count=ticket_count)


@app.route('/shop/buy', methods=['POST'])
@login_required
def shop_buy():
    username = session['user']
    data = request.get_json()
    pid = data.get('product_id')

    products = dm.get_products(active_only=True)
    product = next((p for p in products if p['id'] == pid), None)
    if not product:
        return jsonify({'success': False, 'message': '商品不存在或已下架'})

    price = product['price']
    balance = dm.get_coins_balance(username)
    if balance < price:
        return jsonify({'success': False, 'message': f'金币不足，当前余额 {balance} 个'})

    # 扣金币
    new_bal = dm.add_coins(username, -price, f'购买 {product["name"]}')
    if new_bal is False:
        return jsonify({'success': False, 'message': '金币不足'})

    # 内置商品（免错券）直接发放，无需管理员审核
    if product.get('type') == 'builtin' and pid == 'no_wrong_ticket':
        dm.add_tickets(username, 1)
        return jsonify({'success': True,
                        'message': f'购买成功！免错券 +1，当前余额 {new_bal} 金币',
                        'new_balance': new_bal,
                        'builtin': True})

    # 自定义商品：创建订单等待管理员发货
    oid = dm.create_order(username, pid, product['name'], price)
    return jsonify({'success': True,
                    'message': f'购买成功，请等待管理员发货。当前余额 {new_bal} 金币',
                    'order_id': oid,
                    'new_balance': new_bal})


@app.route('/shop/confirm_receipt', methods=['POST'])
@login_required
def shop_confirm_receipt():
    username = session['user']
    data = request.get_json()
    oid = data.get('order_id')
    orders = dm.get_orders(username=username)
    order = next((o for o in orders if o['id'] == oid), None)
    if not order:
        return jsonify({'success': False, 'message': '订单不存在'})
    if order['status'] != 'shipped':
        return jsonify({'success': False, 'message': '商品尚未发货'})
    dm.update_order_status(oid, 'done')
    return jsonify({'success': True, 'message': '确认收货成功，交易完成！'})


# 管理员：商品管理
@app.route('/admin/shop_products', methods=['GET'])
@admin_required
def admin_shop_products():
    products = dm.get_products(active_only=False)
    orders = dm.get_orders()
    return jsonify({'products': products, 'orders': orders})


@app.route('/admin/shop_add_product', methods=['POST'])
@admin_required
def admin_shop_add_product():
    data = request.get_json()
    name = data.get('name', '').strip()
    desc = data.get('desc', '').strip()
    price = int(data.get('price', 1))
    if not name:
        return jsonify({'success': False, 'message': '商品名称不能为空'})
    pid = dm.add_product(name, desc, price)
    return jsonify({'success': True, 'product_id': pid})


@app.route('/admin/shop_toggle_product', methods=['POST'])
@admin_required
def admin_shop_toggle_product():
    data = request.get_json()
    pid = data.get('product_id')
    active = bool(data.get('active', True))
    dm.toggle_product(pid, active)
    return jsonify({'success': True})


@app.route('/admin/shop_delete_product', methods=['POST'])
@admin_required
def admin_shop_delete_product():
    data = request.get_json()
    pid = data.get('product_id')
    dm.delete_product(pid)
    return jsonify({'success': True})


@app.route('/admin/shop_ship', methods=['POST'])
@admin_required
def admin_shop_ship():
    data = request.get_json()
    oid = data.get('order_id')
    dm.update_order_status(oid, 'shipped')
    return jsonify({'success': True, 'message': '已标记发货'})


# ============================================================
# 许愿池
# ============================================================
@app.route('/wishes')
@login_required
def wishes():
    username = session['user']
    is_admin = dm.is_admin(username)
    wish_list = dm.get_wishes(requester=username, is_admin=is_admin,
                              status_filter=['open', 'approved', 'fulfilled'])
    archived = dm.get_wishes(requester=username, is_admin=is_admin,
                             status_filter=['archived', 'rejected'])
    balance = dm.get_coins_balance(username)
    return render_template('wishes.html',
                           wishes=wish_list,
                           archived=archived,
                           balance=balance,
                           is_admin=is_admin)


@app.route('/wishes/create', methods=['POST'])
@login_required
def wishes_create():
    username = session['user']
    data = request.get_json()
    title = data.get('title', '').strip()
    desc = data.get('desc', '').strip()
    coins = int(data.get('coins', 1))
    is_public = bool(data.get('is_public', True))

    if not title:
        return jsonify({'success': False, 'message': '愿望标题不能为空'})
    if coins < 1:
        return jsonify({'success': False, 'message': '金币数量至少为 1'})

    balance = dm.get_coins_balance(username)
    if balance < coins:
        return jsonify({'success': False, 'message': f'金币不足，当前余额 {balance} 个'})

    new_bal = dm.add_coins(username, -coins, f'许愿：{title}')
    if new_bal is False:
        return jsonify({'success': False, 'message': '金币不足'})

    wid = dm.create_wish(username, title, desc, coins, is_public)
    return jsonify({'success': True, 'wish_id': wid,
                    'message': f'愿望已发出！当前余额 {new_bal} 金币',
                    'new_balance': new_bal})


@app.route('/wishes/pledge', methods=['POST'])
@login_required
def wishes_pledge():
    username = session['user']
    data = request.get_json()
    wid = data.get('wish_id')
    coins = int(data.get('coins', 1))

    wish = dm.get_wish_by_id(wid)
    if not wish:
        return jsonify({'success': False, 'message': '愿望不存在'})
    if wish['status'] not in ('open', 'approved'):
        return jsonify({'success': False, 'message': '该愿望已结束，无法助力'})

    balance = dm.get_coins_balance(username)
    if balance < coins:
        return jsonify({'success': False, 'message': f'金币不足，当前余额 {balance} 个'})

    new_bal = dm.add_coins(username, -coins, f'助力愿望：{wish["title"]}')
    if new_bal is False:
        return jsonify({'success': False, 'message': '金币不足'})

    dm.pledge_wish(wid, username, coins)
    return jsonify({'success': True,
                    'message': f'助力成功！当前余额 {new_bal} 金币',
                    'new_balance': new_bal})


@app.route('/wishes/fulfill', methods=['POST'])
@login_required
def wishes_fulfill():
    """用户标记自己的愿望已实现，归档"""
    username = session['user']
    data = request.get_json()
    wid = data.get('wish_id')
    wish = dm.get_wish_by_id(wid)
    if not wish:
        return jsonify({'success': False, 'message': '愿望不存在'})
    if wish['user'] != username:
        return jsonify({'success': False, 'message': '只能操作自己的愿望'})
    if wish['status'] not in ('open', 'approved'):
        return jsonify({'success': False, 'message': '该愿望状态不可归档'})
    dm.update_wish_status(wid, 'archived')
    return jsonify({'success': True, 'message': '愿望已归档，恭喜你实现了愿望！'})


# 管理员：审批许愿池
@app.route('/admin/wish_approve', methods=['POST'])
@admin_required
def admin_wish_approve():
    data = request.get_json()
    wid = data.get('wish_id')
    dm.update_wish_status(wid, 'approved')
    return jsonify({'success': True, 'message': '愿望已点亮'})


@app.route('/admin/wish_reject', methods=['POST'])
@admin_required
def admin_wish_reject():
    data = request.get_json()
    wid = data.get('wish_id')
    reason = data.get('reason', '').strip()
    wish = dm.get_wish_by_id(wid)
    if not wish:
        return jsonify({'success': False, 'message': '愿望不存在'})
    dm.refund_wish_coins(wid)
    dm.update_wish_status(wid, 'rejected', reason)
    return jsonify({'success': True, 'message': '已驳回并退还金币'})


@app.route('/admin/wish_fulfill', methods=['POST'])
@admin_required
def admin_wish_fulfill():
    """管理员线下完成后标记已实现并归档"""
    data = request.get_json()
    wid = data.get('wish_id')
    wish = dm.get_wish_by_id(wid)
    if not wish:
        return jsonify({'success': False, 'message': '愿望不存在'})
    dm.update_wish_status(wid, 'archived')
    return jsonify({'success': True, 'message': '已将愿望标记为实现并归档'})


@app.route('/admin/wishes_data', methods=['GET'])
@admin_required
def admin_wishes_data():
    """管理员获取全部愿望（含私密）"""
    all_wishes = dm.get_wishes(is_admin=True,
                               status_filter=['open', 'approved', 'fulfilled', 'rejected', 'archived'])
    return jsonify({'wishes': all_wishes})


# 免错券使用接口
@app.route('/coins/use_ticket', methods=['POST'])
@login_required
def use_ticket():
    username = session['user']
    success = dm.use_ticket(username)
    if success:
        remaining = dm.get_ticket_count(username)
        return jsonify({'success': True, 'remaining': remaining,
                        'message': '免错券已使用，本题错误不计入成绩！'})
    return jsonify({'success': False, 'message': '没有可用的免错券'})


@app.route('/study/ticket_override', methods=['POST'])
@login_required
def study_ticket_override():
    """免错券：将当前答错的题目计为正确，并推进"""
    ctx = session.get('study_context')
    if not ctx or ctx['mode'] != 'study':
        return jsonify({'error': '无进行中的学习'}), 400
    # 把错误计数修正：正确数+1，推进index
    ctx['correct_count'] = ctx.get('correct_count', 0) + 1
    ctx['current_index'] += 1
    # 从 wrong_words 中移除（如果有）
    word = ctx['words'][ctx['current_index'] - 1] if ctx['current_index'] > 0 else None
    if word:
        ctx.setdefault('wrong_words', [])
        if word['word'] in ctx['wrong_words']:
            ctx['wrong_words'].remove(word['word'])
    session['study_context'] = ctx
    return jsonify({'success': True})


@app.route('/review/ticket_override', methods=['POST'])
@login_required
def review_ticket_override():
    """免错券：将当前答错的题目计为正确，并推进"""
    ctx = session.get('review_context')
    if not ctx or ctx['mode'] != 'review':
        return jsonify({'error': '无进行中的复习'}), 400
    ctx['correct_count'] = ctx.get('correct_count', 0) + 1
    ctx['current_index'] += 1
    word = ctx['words'][ctx['current_index'] - 1] if ctx['current_index'] > 0 else None
    if word:
        ctx.setdefault('wrong_words', [])
        if word['word'] in ctx['wrong_words']:
            ctx['wrong_words'].remove(word['word'])
    session['review_context'] = ctx
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
