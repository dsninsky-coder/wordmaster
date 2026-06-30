import json
import os
import csv
import io
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash


class DataManager:
    DATA_DIR = "data"
    USER_FILE = os.path.join(DATA_DIR, "user.json")
    CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
    WORDS_FILE = os.path.join(DATA_DIR, "words.json")
    HISTORY_DIR = os.path.join(DATA_DIR, "history")
    ADMIN_CONFIG_FILE = os.path.join(DATA_DIR, "admin_config.json")

    def __init__(self):
        os.makedirs(self.DATA_DIR, exist_ok=True)
        os.makedirs(self.HISTORY_DIR, exist_ok=True)
        self._init_default_files()

    def _init_default_files(self):
        if not os.path.exists(self.USER_FILE):
            default_users = {
                "admin": {
                    "password": generate_password_hash("admin"),
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "is_admin": True
                }
            }
            with open(self.USER_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_users, f, indent=2, ensure_ascii=False)

        if not os.path.exists(self.CONFIG_FILE):
            default_config = {
                "review_count": 20,
                "chatgpt_api_key": "",
                "chatgpt_base_url": "https://api.openai.com/v1",
                "require_review_before_study": False,
                "require_both_modes": False
            }
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2)

        if not os.path.exists(self.WORDS_FILE):
            default_words = {
                "list1": [
                    {"word": "apple", "meaning": "苹果"},
                    {"word": "boy", "meaning": "男孩"},
                    {"word": "cat", "meaning": "猫"}
                ],
                "list2": [
                    {"word": "dog", "meaning": "狗"},
                    {"word": "book", "meaning": "书"}
                ]
            }
            with open(self.WORDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_words, f, indent=2, ensure_ascii=False)

        if not os.path.exists(self.ADMIN_CONFIG_FILE):
            default_admin = {
                "shared_api_key": "",
                "shared_base_url": "https://api.openai.com/v1",
                "allowed_api_users": [],      # 允许使用共享API的用户列表
                "retry_cooldown_seconds": 60, # 未通过后重答冷却时间（秒）
                "controlled_users": {}        # { username: { field: value, ... } }
            }
            with open(self.ADMIN_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_admin, f, indent=2, ensure_ascii=False)

    # ---------- 用户管理 ----------
    def load_users(self):
        with open(self.USER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_users(self, users):
        with open(self.USER_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=2, ensure_ascii=False)

    def verify_user(self, username, password):
        users = self.load_users()
        if username not in users:
            return False
        user_data = users[username]
        if isinstance(user_data, str):
            return user_data == password
        return check_password_hash(user_data["password"], password)

    def is_admin(self, username):
        users = self.load_users()
        if username not in users:
            return False
        user_data = users[username]
        if isinstance(user_data, dict):
            return user_data.get("is_admin", False)
        return False

    def register_user(self, username, password):
        if not username or len(username) < 2:
            return False, "用户名至少2个字符"
        if not password or len(password) < 4:
            return False, "密码至少4个字符"
        users = self.load_users()
        if username in users:
            return False, "用户名已存在"
        users[username] = {
            "password": generate_password_hash(password),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "is_admin": False
        }
        self.save_users(users)
        return True, "注册成功"

    def change_password(self, username, old_password, new_password):
        if not self.verify_user(username, old_password):
            return False, "原密码错误"
        if len(new_password) < 4:
            return False, "新密码至少4个字符"
        users = self.load_users()
        users[username]["password"] = generate_password_hash(new_password)
        self.save_users(users)
        return True, "密码修改成功"

    def admin_reset_password(self, target_username, new_password):
        """管理员直接重置任意用户密码（无需旧密码）"""
        users = self.load_users()
        if target_username not in users:
            return False, f"用户 {target_username} 不存在"
        if len(new_password) < 4:
            return False, "新密码至少4个字符"
        users[target_username]["password"] = generate_password_hash(new_password)
        self.save_users(users)
        return True, f"已成功重置用户 {target_username} 的密码"

    def get_all_usernames(self):
        users = self.load_users()
        return [u for u in users.keys() if not self.is_admin(u)]

    # ---------- 全局配置 ----------
    def load_config(self):
        with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        cfg.setdefault("chatgpt_base_url", "https://api.openai.com/v1")
        return cfg

    def save_config(self, config):
        with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    # ---------- 超管配置 ----------
    def load_admin_config(self):
        with open(self.ADMIN_CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        cfg.setdefault("shared_api_key", "")
        cfg.setdefault("shared_base_url", "https://api.openai.com/v1")
        cfg.setdefault("allowed_api_users", [])
        cfg.setdefault("retry_cooldown_seconds", 60)
        cfg.setdefault("controlled_users", {})
        cfg.setdefault("tts_in_en2zh", False)
        cfg.setdefault("audio2zh_enabled", True)
        return cfg

    def save_admin_config(self, cfg):
        with open(self.ADMIN_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)

    def get_effective_config(self, username):
        """
        获取用户最终生效的配置：
        - 先取用户自己的设置（config.json 默认值 + 个人存储）
        - 再被超管控制覆盖
        返回 (config_dict, controlled_fields_set)
        """
        base = self.load_config()
        user_history = self.load_user_history(username)
        user_prefs = user_history.get("user_prefs", {})

        # 用户个人设置覆盖全局默认
        merged = dict(base)
        for k, v in user_prefs.items():
            merged[k] = v

        # 超管覆盖
        admin_cfg = self.load_admin_config()
        controlled = admin_cfg.get("controlled_users", {}).get(username, {})
        controlled_fields = set(controlled.keys())
        for k, v in controlled.items():
            merged[k] = v

        # 共享AI：如果用户在允许列表中，使用共享API
        if username in admin_cfg.get("allowed_api_users", []):
            if admin_cfg.get("shared_api_key"):
                merged["chatgpt_api_key"] = admin_cfg["shared_api_key"]
                merged["chatgpt_base_url"] = admin_cfg.get("shared_base_url", "https://api.openai.com/v1")
                merged["ai_model"] = admin_cfg.get("shared_ai_model", "deepseek-chat")
                controlled_fields.add("chatgpt_api_key")
                controlled_fields.add("chatgpt_base_url")
                controlled_fields.add("ai_model")

        return merged, controlled_fields

    def save_user_prefs(self, username, prefs):
        """保存用户个人设置偏好（存入历史文件中）"""
        history = self.load_user_history(username)
        history["user_prefs"] = prefs
        self.save_user_history(username, history)

    # ---------- 单词库 ----------
    def load_words(self):
        with open(self.WORDS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_words(self, words):
        with open(self.WORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(words, f, indent=2, ensure_ascii=False)

    def import_words_from_data(self, rows, overwrite=False):
        words = self.load_words()
        imported = 0
        skipped = 0
        list_names = set()

        for row in rows:
            list_name = row.get("list", "").strip()
            word = row.get("word", "").strip()
            meaning = row.get("meaning", "").strip()

            if not list_name or not word or not meaning:
                skipped += 1
                continue

            if list_name not in words:
                words[list_name] = []

            existing = [w for w in words[list_name] if w["word"].lower() == word.lower()]
            if existing:
                if overwrite:
                    existing[0]["meaning"] = meaning
                    imported += 1
                else:
                    skipped += 1
                continue

            words[list_name].append({"word": word, "meaning": meaning})
            list_names.add(list_name)
            imported += 1

        self.save_words(words)
        return imported, skipped, list(list_names)

    def parse_csv_content(self, content, encoding='utf-8'):
        rows = []
        try:
            text = content.decode(encoding) if isinstance(content, bytes) else content
        except UnicodeDecodeError:
            text = content.decode('gbk', errors='replace')

        reader = csv.DictReader(io.StringIO(text))
        headers = [h.strip().lower() for h in (reader.fieldnames or [])]

        field_map = {}
        for h in headers:
            if h in ['list', 'list_name', '列表', '分组']:
                field_map['list'] = h
            elif h in ['word', '单词', 'english', '英文', 'en']:
                field_map['word'] = h
            elif h in ['meaning', '释义', '中文', 'chinese', 'zh', '翻译']:
                field_map['meaning'] = h

        for row in reader:
            clean_row = {k.strip().lower(): v.strip() for k, v in row.items() if v}
            entry = {}
            entry['list'] = clean_row.get(field_map.get('list', ''), '').strip()
            entry['word'] = clean_row.get(field_map.get('word', ''), '').strip()
            entry['meaning'] = clean_row.get(field_map.get('meaning', ''), '').strip()
            if entry['word'] and entry['meaning']:
                rows.append(entry)

        return rows

    def parse_txt_content(self, content, default_list='list1'):
        rows = []
        try:
            text = content.decode('utf-8') if isinstance(content, bytes) else content
        except UnicodeDecodeError:
            text = content.decode('gbk', errors='replace')

        current_list = default_list
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('[') and line.endswith(']'):
                current_list = line[1:-1].strip()
                continue
            for sep in ['=', '\t', ',']:
                if sep in line:
                    parts = line.split(sep, 1)
                    if len(parts) == 2:
                        word, meaning = parts[0].strip(), parts[1].strip()
                        if word and meaning:
                            rows.append({"list": current_list, "word": word, "meaning": meaning})
                        break

        return rows

    def get_list_names(self):
        return list(self.load_words().keys())

    def get_list_word_count(self):
        words = self.load_words()
        return {k: len(v) for k, v in words.items()}

    # ---------- 用户历史 ----------
    def _get_user_history_path(self, username):
        return os.path.join(self.HISTORY_DIR, f"{username}.json")

    def load_user_history(self, username):
        path = self._get_user_history_path(username)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {}

        data.setdefault("learned_lists", [])
        data.setdefault("word_reviews", {})
        data.setdefault("quiz_results", [])
        data.setdefault("daily_stats", {})
        data.setdefault("user_prefs", {})
        data.setdefault("list_cooldowns", {})  # { list_name: ISO datetime str }
        data.setdefault("review_once_cleared_date", "")  # "once" 模式：复习已完成的日期
        return data

    # ---------- "复习一次即可"模式：标记今日已通过 ----------
    def set_review_once_cleared(self, username):
        """标记今日复习已完成（once 模式）"""
        history = self.load_user_history(username)
        history["review_once_cleared_date"] = datetime.now().strftime("%Y-%m-%d")
        self.save_user_history(username, history)

    def is_review_once_cleared(self, username):
        """今日是否已经完成过一次达标复习（once 模式）"""
        history = self.load_user_history(username)
        cleared_date = history.get("review_once_cleared_date", "")
        today = datetime.now().strftime("%Y-%m-%d")
        return cleared_date == today

    def save_user_history(self, username, history):
        path = self._get_user_history_path(username)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

    def add_learned_list(self, username, list_name):
        history = self.load_user_history(username)
        if list_name not in history["learned_lists"]:
            history["learned_lists"].append(list_name)
        self.save_user_history(username, history)

    def is_list_learned(self, username, list_name):
        history = self.load_user_history(username)
        return list_name in history["learned_lists"]

    # ---------- 答题冷却 ----------
    def set_list_cooldown(self, username, list_name, seconds):
        """答题未通过后，设置冷却时间"""
        history = self.load_user_history(username)
        cooldown_until = (datetime.now() + timedelta(seconds=seconds)).strftime("%Y-%m-%d %H:%M:%S")
        history["list_cooldowns"][list_name] = cooldown_until
        self.save_user_history(username, history)

    def get_list_cooldown_remaining(self, username, list_name):
        """
        返回还需等待的秒数，0 表示可以答题
        """
        history = self.load_user_history(username)
        cooldown_str = history.get("list_cooldowns", {}).get(list_name)
        if not cooldown_str:
            return 0
        try:
            cooldown_until = datetime.strptime(cooldown_str, "%Y-%m-%d %H:%M:%S")
            remaining = (cooldown_until - datetime.now()).total_seconds()
            return max(0, int(remaining))
        except Exception:
            return 0

    def clear_list_cooldown(self, username, list_name):
        history = self.load_user_history(username)
        history.get("list_cooldowns", {}).pop(list_name, None)
        self.save_user_history(username, history)

    # ---------- 遗忘曲线 ----------
    def update_word_review(self, username, list_name, word, correct):
        history = self.load_user_history(username)
        key = f"{list_name}:{word}"
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        if key not in history["word_reviews"]:
            history["word_reviews"][key] = {
                "last_review": today_str,
                "review_count": 0,
                "correct_count": 0,
                "ease_factor": 2.5,
                "interval": 1,
                "next_review": today_str
            }

        rec = history["word_reviews"][key]
        rec["last_review"] = today_str
        rec["review_count"] += 1

        if correct:
            rec["correct_count"] += 1
            if rec["review_count"] == 1:
                rec["interval"] = 1
            elif rec["review_count"] == 2:
                rec["interval"] = 6
            else:
                rec["interval"] = max(1, int(rec["interval"] * rec["ease_factor"]))
            rec["interval"] = min(rec["interval"], 180)
            rec["next_review"] = (now + timedelta(days=rec["interval"])).strftime("%Y-%m-%d")
        else:
            rec["interval"] = 1
            # 答错：next_review 保持为今天，使该单词仍处于"待复习"状态
            # 下一次复习会话开始时，此单词仍会被纳入抽取池
            rec["next_review"] = today_str
            rec["ease_factor"] = max(1.3, rec["ease_factor"] - 0.2)

        self.save_user_history(username, history)

    def get_review_words(self, username, limit=20):
        history = self.load_user_history(username)
        now = datetime.now().strftime("%Y-%m-%d")
        words_data = self.load_words()
        review_list = []

        for key, rec in history["word_reviews"].items():
            if rec.get("next_review", "9999-99-99") <= now:
                parts = key.split(":", 1)
                if len(parts) != 2:
                    continue
                list_name, word = parts
                if list_name in words_data:
                    for item in words_data[list_name]:
                        if item["word"] == word:
                            review_list.append({
                                "list": list_name,
                                "word": word,
                                "meaning": item["meaning"],
                                "next_review": rec.get("next_review", ""),
                                "interval": rec.get("interval", 1)
                            })
                            break

        review_list.sort(key=lambda x: x["next_review"])
        if len(review_list) > limit:
            import random
            review_list = random.sample(review_list, limit)
        return review_list

    def get_review_count(self, username):
        history = self.load_user_history(username)
        now = datetime.now().strftime("%Y-%m-%d")
        count = 0
        for key, rec in history["word_reviews"].items():
            if rec.get("next_review", "9999-99-99") <= now:
                count += 1
        return count

    # ---------- 成绩记录 ----------
    def add_quiz_result(self, username, list_name, correct, total, mode="study", quiz_mode="en2zh"):
        """
        mode: "study" | "review"
        quiz_mode: "en2zh" | "zh2en"（答题方向）
        """
        history = self.load_user_history(username)
        now = datetime.now()
        record = {
            "time": now.strftime("%Y-%m-%d %H:%M"),
            "list": list_name,
            "correct": correct,
            "total": total,
            "score": f"{correct}/{total}",
            "percent": round(correct / total * 100, 1) if total > 0 else 0,
            "mode": mode,
            "quiz_mode": quiz_mode,   # 新增：答题方向
            "passed": (correct / total >= 0.8) if total > 0 else False
        }
        history["quiz_results"].append(record)

        today = now.strftime("%Y-%m-%d")
        daily = history["daily_stats"].setdefault(today, {
            "studied_lists": [],
            "review_passed": False,
            "review_done": False,
            "quiz_count": 0
        })
        if mode == "study" and list_name not in daily["studied_lists"]:
            daily["studied_lists"].append(list_name)
        if mode == "review":
            daily["review_done"] = True
            if record["passed"]:
                daily["review_passed"] = True
        daily["quiz_count"] += 1

        self.save_user_history(username, history)

    def get_daily_status(self, username):
        history = self.load_user_history(username)
        result = {}
        for date_str, daily in history.get("daily_stats", {}).items():
            studied = len(daily.get("studied_lists", [])) > 0
            review_done = daily.get("review_done", False)
            review_passed = daily.get("review_passed", False)

            if studied:
                if not review_done or review_passed:
                    result[date_str] = "green"
                else:
                    result[date_str] = "red"
            elif review_done:
                result[date_str] = "red" if not review_passed else "green"

        return result

    # ============================================================
    # 金币系统
    # ============================================================
    COINS_FILE = os.path.join("data", "coins.json")         # 用户金币余额 + 流水
    SHOP_FILE  = os.path.join("data", "shop.json")          # 商品列表 + 订单
    WISH_FILE  = os.path.join("data", "wishes.json")        # 许愿池

    def _ensure_coins_file(self):
        if not os.path.exists(self.COINS_FILE):
            with open(self.COINS_FILE, 'w', encoding='utf-8') as f:
                json.dump({}, f)

    def _ensure_shop_file(self):
        if not os.path.exists(self.SHOP_FILE):
            default = {
                "products": [
                    {
                        "id": "no_wrong_ticket",
                        "name": "免错机会券",
                        "desc": "答错时可消耗此券抵消本次错误，不计入成绩",
                        "price": 2,
                        "type": "builtin",
                        "unlimited": True,
                        "active": True
                    }
                ],
                "orders": []
            }
            with open(self.SHOP_FILE, 'w', encoding='utf-8') as f:
                json.dump(default, f, indent=2, ensure_ascii=False)

    def _ensure_wish_file(self):
        if not os.path.exists(self.WISH_FILE):
            with open(self.WISH_FILE, 'w', encoding='utf-8') as f:
                json.dump({"wishes": []}, f, indent=2, ensure_ascii=False)

    # ---- 金币余额 ----
    def _load_coins_db(self):
        self._ensure_coins_file()
        with open(self.COINS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_coins_db(self, db):
        with open(self.COINS_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)

    def _get_user_coins_entry(self, db, username):
        if username not in db:
            db[username] = {"balance": 0, "ledger": [], "checkin": {}}
        db[username].setdefault("balance", 0)
        db[username].setdefault("ledger", [])
        db[username].setdefault("checkin", {})
        return db[username]

    def get_coins_balance(self, username):
        db = self._load_coins_db()
        entry = self._get_user_coins_entry(db, username)
        return entry["balance"]

    def add_coins(self, username, amount, reason):
        """增加金币，amount 可为负（消费）。返回新余额或 False（余额不足）"""
        db = self._load_coins_db()
        entry = self._get_user_coins_entry(db, username)
        if entry["balance"] + amount < 0:
            return False
        entry["balance"] += amount
        entry["ledger"].append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "amount": amount,
            "reason": reason,
            "balance": entry["balance"]
        })
        self._save_coins_db(db)
        return entry["balance"]

    def get_coins_ledger(self, username, limit=50):
        db = self._load_coins_db()
        entry = self._get_user_coins_entry(db, username)
        return list(reversed(entry["ledger"][-limit:]))

    # ---- 每日打卡记录 ----
    def get_checkin_status(self, username):
        """返回今日已领取的打卡项集合：{'login', 'study', 'review'}"""
        db = self._load_coins_db()
        entry = self._get_user_coins_entry(db, username)
        today = datetime.now().strftime("%Y-%m-%d")
        return set(entry["checkin"].get(today, []))

    def mark_checkin(self, username, item):
        """标记今日某项打卡已完成（item: 'login'/'study'/'review'）"""
        db = self._load_coins_db()
        entry = self._get_user_coins_entry(db, username)
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in entry["checkin"]:
            entry["checkin"][today] = []
        if item not in entry["checkin"][today]:
            entry["checkin"][today].append(item)
        self._save_coins_db(db)

    def try_grant_checkin(self, username, item, coins, reason):
        """若今日未领取该项，则发放金币并标记。返回 (granted, new_balance)"""
        done = self.get_checkin_status(username)
        if item in done:
            return False, self.get_coins_balance(username)
        new_bal = self.add_coins(username, coins, reason)
        self.mark_checkin(username, item)
        return True, new_bal

    # ---- 免错券库存 ----
    def get_ticket_count(self, username):
        """免错券数量（存在 user history）"""
        history = self.load_user_history(username)
        return history.get("no_wrong_tickets", 0)

    def add_tickets(self, username, n):
        history = self.load_user_history(username)
        history["no_wrong_tickets"] = history.get("no_wrong_tickets", 0) + n
        self.save_user_history(username, history)

    def use_ticket(self, username):
        """消耗一张免错券，成功返回 True"""
        history = self.load_user_history(username)
        cnt = history.get("no_wrong_tickets", 0)
        if cnt <= 0:
            return False
        history["no_wrong_tickets"] = cnt - 1
        self.save_user_history(username, history)
        return True

    # ============================================================
    # 商城
    # ============================================================
    def load_shop(self):
        self._ensure_shop_file()
        with open(self.SHOP_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_shop(self, shop):
        with open(self.SHOP_FILE, 'w', encoding='utf-8') as f:
            json.dump(shop, f, indent=2, ensure_ascii=False)

    def get_products(self, active_only=True):
        shop = self.load_shop()
        prods = shop.get("products", [])
        if active_only:
            prods = [p for p in prods if p.get("active", True)]
        return prods

    def add_product(self, name, desc, price):
        shop = self.load_shop()
        pid = f"prod_{int(datetime.now().timestamp()*1000)}"
        shop["products"].append({
            "id": pid,
            "name": name,
            "desc": desc,
            "price": price,
            "type": "custom",
            "unlimited": True,
            "active": True
        })
        self.save_shop(shop)
        return pid

    def toggle_product(self, pid, active):
        shop = self.load_shop()
        for p in shop["products"]:
            if p["id"] == pid:
                p["active"] = active
                break
        self.save_shop(shop)

    def delete_product(self, pid):
        shop = self.load_shop()
        shop["products"] = [p for p in shop["products"] if p["id"] != pid]
        self.save_shop(shop)

    def create_order(self, username, product_id, product_name, price):
        """下单购买（金币已提前扣除），返回订单 id"""
        shop = self.load_shop()
        oid = f"ord_{int(datetime.now().timestamp()*1000)}"
        shop.setdefault("orders", []).append({
            "id": oid,
            "user": username,
            "product_id": product_id,
            "product_name": product_name,
            "price": price,
            "status": "pending",   # pending → shipped → done
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "shipped_at": "",
            "done_at": ""
        })
        self.save_shop(shop)
        return oid

    def get_orders(self, username=None, status=None):
        shop = self.load_shop()
        orders = shop.get("orders", [])
        if username:
            orders = [o for o in orders if o["user"] == username]
        if status:
            orders = [o for o in orders if o["status"] == status]
        return list(reversed(orders))

    def update_order_status(self, oid, status):
        shop = self.load_shop()
        for o in shop.get("orders", []):
            if o["id"] == oid:
                o["status"] = status
                if status == "shipped":
                    o["shipped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                elif status == "done":
                    o["done_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break
        self.save_shop(shop)

    # ============================================================
    # 许愿池
    # ============================================================
    def load_wishes(self):
        self._ensure_wish_file()
        with open(self.WISH_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_wishes(self, data):
        with open(self.WISH_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def create_wish(self, username, title, desc, coins, is_public):
        data = self.load_wishes()
        wid = f"wish_{int(datetime.now().timestamp()*1000)}"
        data["wishes"].append({
            "id": wid,
            "user": username,
            "title": title,
            "desc": desc,
            "coins": coins,          # 用户投入金币
            "pledged_coins": coins,  # 实际已汇集（本人+助力）
            "pledges": [{            # 助力记录
                "user": username,
                "coins": coins,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }],
            "is_public": is_public,
            "status": "open",        # open | approved | rejected | fulfilled | archived
            "lit": False,            # 管理员点亮
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "reject_reason": ""
        })
        self.save_wishes(data)
        return wid

    def get_wishes(self, requester=None, is_admin=False, status_filter=None):
        """
        requester: 当前访问者用户名
        is_admin: 是否管理员（可看私密）
        """
        data = self.load_wishes()
        result = []
        for w in reversed(data["wishes"]):
            if status_filter and w["status"] not in status_filter:
                continue
            # 可见性：公开 or 是自己的 or 管理员
            if not w["is_public"] and not is_admin and w["user"] != requester:
                continue
            result.append(w)
        return result

    def get_wish_by_id(self, wid):
        data = self.load_wishes()
        for w in data["wishes"]:
            if w["id"] == wid:
                return w
        return None

    def pledge_wish(self, wid, username, coins):
        """助力：追加金币（金币已提前扣除）"""
        data = self.load_wishes()
        for w in data["wishes"]:
            if w["id"] == wid:
                w["pledged_coins"] = w.get("pledged_coins", w["coins"]) + coins
                w["pledges"].append({
                    "user": username,
                    "coins": coins,
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                w["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break
        self.save_wishes(data)

    def update_wish_status(self, wid, status, reason=""):
        data = self.load_wishes()
        for w in data["wishes"]:
            if w["id"] == wid:
                w["status"] = status
                if status == "approved":
                    w["lit"] = True
                if reason:
                    w["reject_reason"] = reason
                w["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break
        self.save_wishes(data)

    def refund_wish_coins(self, wid):
        """驳回愿望时，将所有已投入金币退还给各助力者"""
        data = self.load_wishes()
        for w in data["wishes"]:
            if w["id"] == wid:
                for pledge in w.get("pledges", []):
                    self.add_coins(pledge["user"], pledge["coins"],
                                   f"愿望被驳回退款：{w['title']}")
                return True
        return False

    def get_all_usernames_with_admin(self):
        """包含管理员的全用户列表"""
        users = self.load_users()
        return list(users.keys())
