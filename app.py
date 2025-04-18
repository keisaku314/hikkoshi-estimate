# app.py
from flask import Flask, render_template, request, session, make_response, redirect, url_for, flash, Response
from datetime import timedelta
import json, os
import csv

from uuid import uuid4
from datetime import datetime

HISTORY_FILE = "history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return []

def save_history_entry(entry):
    history = load_history()
    history.insert(0, entry)  # 新しいものを先頭に
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

CONFIG_FILE = "admin_config.json"

# 設定をファイルから読み込む
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            # 壊れてたら初期化
            return {
                "worker_fee": 20000,
                "truck_costs": {
                    "軽トラック": 10000,
                    "2tショート": 30000,
                    "2tロング": 30000,
                    "2tロングワイド": 30000,
                }
            }
    else:
        return {
            "worker_fee": 20000,
            "truck_costs": {
                "軽トラック": 10000,
                "2tショート": 30000,
                "2tロング": 30000,
                "2tロングワイド": 30000,
            }
        }

# 設定をファイルに保存する
def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

app = Flask(__name__)
app.secret_key = 'your-secret-key'
app.permanent_session_lifetime = timedelta(minutes=10)

# 荷物ごとのポイント（上位10件）
ITEM_POINTS = {
    "洋服タンス（1枚扉）": 36,
    "洋服タンス（2枚扉）": 44,
    "洋服タンス（3枚扉以上）": 60,
    "整理タンス・チェスト（大）": 55,
    "整理タンス・チェスト（中）": 37,
    "教理タンス・チェスト（小）": 14,
    "和タンス": 55,
    "ローボード": 14,
    "サイドボード": 42,
    "ベッド（シングル）": 50,
    "ベッド（セミダブル）": 70,
    "ベッド（ダブル）": 80,
    "ベッド（2段）": 70,
    "ソファー（1人）": 20,
    "ソファー（2人）": 45,
    "ソファー（3人）": 57,
    "ソファーベッド": 60,
    "机": 40,
    "回転イス": 15,
    "本棚（大）": 44,
    "本棚（中）": 29,
    "本棚（小）": 16,
    "スチールラック（大）": 44,
    "スチールラック（中）": 29,
    "スチールラック（小）": 16,
    "すきま家具": 8,
    "カラーボックス": 5,
    "コタツ・テーブル": 15,
    "食卓": 30,
    "イス": 5,
    "食器棚（大）": 52,
    "食器棚（中）": 42,
    "食器棚（小）": 22,
    "カウンター": 15,
    "レンジ or トースター": 2,
    "レンジ台": 15,
    "冷蔵庫（大）": 43,
    "冷蔵庫（小）": 13,
    "洗濯機": 20,
    "乾燥機": 8,
    "テレビ（大）": 15,
    "テレビ（中）": 10,
    "テレビ（小）": 2,
    "テレビ台（大）": 30,
    "テレビ台（中）": 10,
    "テレビ台（小）": 5,
    "オーディオ": 5,
    "パソコン": 5,
    "パソコンラック": 10,
    "衣装ケース1段": 5,
    "衣装ケース3段": 15,
    "衣装ケース4段": 20,
    "衣装ケース5段": 25,
    "押入れタンス": 15,
    "エアコン": 9,
    "照明": 3,
    "布団袋": 10,
    "ダンボール（大）": 3,
    "ダンボール（小）": 2,
    "自転車": 35,
    "バイク（原付）": 40,
    "バイク（中型以上）": 60,
    "アップライトピアノ": 80,
    "電子ピアノ": 40,
    "タイヤ（4本）": 20,
    "物置（大）": 200,
    "物置（小）": 50,
    "植木鉢": 3,
    "お仏壇": 30,
    "カーペット": 6,
    "下駄箱（大）": 20,
    "下駄箱（小）": 10,
    "姿見": 2,
    "小型家電": 3,
    "パイプハンガー": 3,
    "扇風機": 3,
    "ハンガーボックス": 15,
    "ゴルフバッグ": 6,
    "スーツケース": 5,
}


# トラック種別とポイント上限・車両費
TRUCK_TYPES = [
    {"name": "軽トラック", "capacity": 200, "cost": 10000},
    {"name": "2tショート", "capacity": 500, "cost": 30000},
    {"name": "2tロング", "capacity": 700, "cost": 30000},
    {"name": "2tロングワイド", "capacity": 900, "cost": 30000},
]

def get_worker_count(points):
    if points <= 200:
        return 1
    elif points <= 500:
        return 2
    elif points <= 900:
        return 3
    return 0

def get_distance_multiplier(distance):
    if distance <= 10:
        return 1.0
    else:
        return 1.0 + ((distance - 1) // 10) * 0.5

@app.route("/", methods=["GET", "POST"])
def index():
    # フォーム入力を維持するための変数
    form_data = {}
    result = None

    if request.method == "POST":

        # jsonから管理設定を取得
        admin_config = load_config()
        worker_fee = admin_config.get("worker_fee", 20000)
        truck_costs = admin_config.get("truck_costs", {})

        
        form_data = request.form.to_dict()
        # 担当者 & シーズン & キャンペーンコード
        staff = request.form.get("staff", "")
        season = request.form.get("season", "normal")  # normal or peak
        campaign_code = request.form.get("campaign_code", "")
        
        # ユーザー情報
        name = request.form["name"]
        phone = request.form["phone"]
        from_address = request.form["from_address"]
        to_address = request.form["to_address"]
        distance = int(request.form["distance"])
        remarks = request.form["remarks"]

        # 日程関連（引越し元）
        from_date = request.form["from_date"]
        from_time_period = request.form.get("from_time_period", "")
        from_time_memo = request.form.get("from_time_memo", "")

         # 日程関連（引越し先）
        to_date = request.form["to_date"]
        to_time_period = request.form.get("to_time_period", "")
        to_time_memo = request.form.get("to_time_memo", "")
        
        # 荷物処理
        items = []
        total_points = 0
        for item, pt in ITEM_POINTS.items():
            count = int(request.form.get(item, 0))
            if count > 0:
                points = pt * count
                total_points += points
                items.append({"name": item, "count": count, "points": points})

        # トラック割り当て
        trucks = []
        remaining = total_points
        while remaining > 0:
            for truck in reversed(TRUCK_TYPES):
                if remaining > truck["capacity"]:
                    trucks.append(truck)
                    remaining -= truck["capacity"]
                    break
            else:
                for truck in TRUCK_TYPES:
                    if remaining <= truck["capacity"]:
                        trucks.append(truck)
                        remaining = 0
                        break

        total_workers = 0
        truck_point_splits = []
        temp_remaining = total_points
        for truck in trucks:
            cap = truck["capacity"]
            pts = cap if temp_remaining > cap else temp_remaining
            workers = get_worker_count(pts)
            truck_point_splits.append({
                "truck": {"name": truck["name"], "capacity": cap, "cost": truck["cost"]},
                "points": pts,
                "workers": workers
            })
            total_workers += workers
            temp_remaining -= pts
            
        # 繁忙期 or 通常期で費用を切り替え
        # たとえば繁忙期だと +20% (係数1.2)
        # 作業員費(20000円) → 繁忙期なら 24000円
        # 車両費 → truck["cost"] * 1.2
        if season == "peak":
            season_factor = 1.2
        else:
            season_factor = 1.0

        # 距離係数
        distance_multiplier = get_distance_multiplier(distance)

        # 車両費 + 作業員費
        vehicle_cost = 0
        for t in truck_point_splits:
            truck_name = t["truck"]["name"]
            base_cost = truck_costs.get(truck_name, t["truck"]["cost"])  # セッションの設定を優先
            # 距離係数×シーズン係数
            cost = base_cost * distance_multiplier * season_factor
            vehicle_cost += cost

        # 作業員費
        worker_cost = total_workers * worker_fee * season_factor

        # 小計
        total_cost = int(vehicle_cost + worker_cost)

        # 税込
        total_cost_with_tax = int(total_cost * 1.1)

        # ★ キャンペーンコードで値引き ★
        #  - 0.1 ~ 0.9 → 乗算割引 (10%~90%オフ)
        #  - 1以上      → 差し引き (例 5000 => 5000円引)
        discount_code_value = 0
        try:
            discount_code_value = float(campaign_code)
        except ValueError:
            pass  # 数値以外なら0として無視

        final_cost = total_cost_with_tax
        if 0.1 <= discount_code_value < 1.0:
            # 乗算割引
            final_cost = int(final_cost * discount_code_value)
        elif discount_code_value >= 1.0:
            # 差し引き
            final_cost = final_cost - discount_code_value
            if final_cost < 0:
                final_cost = 0  # マイナスにならないように

        # 結果まとめ
        result = {
            "staff": staff,
            "season": season,
            "campaign_code": campaign_code,

            "name": name,
            "phone": phone,
            "from_address": from_address,
            "to_address": to_address,
            "distance": distance,
            "remarks": remarks,

            "from_date": from_date,
            "from_time_period": from_time_period,
            "from_time_memo": from_time_memo,

            "to_date": to_date,
            "to_time_period": to_time_period,
            "to_time_memo": to_time_memo,

            "items": items,
            "total_points": total_points,
            "truck_point_splits": truck_point_splits,
            "total_workers": total_workers,

            "vehicle_cost": int(vehicle_cost),
            "worker_cost": int(worker_cost),
            "total_cost": total_cost,
            "total_cost_with_tax": total_cost_with_tax,
            "final_cost": int(final_cost),
        }

        # 履歴として保存
        history_entry = {
        "id": str(uuid4()),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "name": name,
        "total_cost_with_tax": total_cost_with_tax,
        "data": result
        }
        save_history_entry(history_entry)


        # セッションに保存
        session["latest_result"] = json.dumps(result, ensure_ascii=False)

        # フォーム入力を維持したいので form_data に格納して再度レンダリング時に渡す
        form_data = request.form.to_dict()

    else:
        # GET の場合、もしセッションにデータあればフォーム初期表示に反映
        if "latest_result" in session:
            saved = json.loads(session["latest_result"])
            # ここで必要なら少し補完
            form_data = {
            "staff": saved.get("staff", ""),
            "season": saved.get("season", "normal"),
            "campaign_code": saved.get("campaign_code", ""),
            "name": saved.get("name", ""),
            "phone": saved.get("phone", ""),
            "from_address": saved.get("from_address", ""),
            "to_address": saved.get("to_address", ""),
            "distance": str(saved.get("distance", "0")),
            "remarks": saved.get("remarks", ""),
            "from_date": saved.get("from_date", ""),
            "from_time_period": saved.get("from_time_period", ""),
            "from_time_memo": saved.get("from_time_memo", ""),
            "to_date": saved.get("to_date", ""),
            "to_time_period": saved.get("to_time_period", ""),
            "to_time_memo": saved.get("to_time_memo", ""),
            }
            for item, pt in ITEM_POINTS.items():
                # itemsの中にあるなら入れておく
                # input nameは item
                count = 0
                for i in saved.get("items", []):
                    if i["name"] == item:
                        count = i["count"]
                form_data[item] = str(count)

                
    return render_template("index.html", items=ITEM_POINTS, result=result, form_data=form_data)

@app.route("/view_estimate")
def view_estimate():
    if "latest_result" not in session:
        return "見積もりデータが見つかりません", 400
    result = json.loads(session["latest_result"])
    return render_template("estimate_view.html", result=result)

# 履歴一覧ページのルートを追加
@app.route("/admin/history")
def view_history():
    history = load_history()
    return render_template("history.html", history=history)

# 詳細ページ（個別表示）
@app.route("/admin/history/<history_id>")
def view_history_detail(history_id):
    history = load_history()
    for h in history:
        if h["id"] == history_id:
            return render_template("estimate_view.html", result=h["data"])
    return "見積もりが見つかりませんでした", 404

#履歴削除機能
@app.route("/admin/history/<history_id>/delete", methods=["POST"])
def delete_history_entry(history_id):
    history = load_history()
    new_history = [h for h in history if h["id"] != history_id]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(new_history, f, ensure_ascii=False, indent=2)
    flash("履歴を削除しました。", "success")
    return redirect(url_for("view_history"))

# 管理画面で使う初期設定（何も保存されていないときの値）
DEFAULT_ADMIN_CONFIG = {
    "worker_fee": 20000,
    "truck_costs": {
        "軽トラック": 10000,
        "2tショート": 30000,
        "2tロング": 30000,
        "2tロングワイド": 30000,
    }
}

# /admin にアクセスすると管理画面が表示される
@app.route("/admin", methods=["GET", "POST"])
def admin():
    # 現在の設定をセッションから取得（なければ初期値を使う）
    config = load_config()

    if request.method == "POST":
        try:
            # フォームから値を受け取って数値化
            worker_fee = int(request.form.get("worker_fee", 20000))
            truck_costs = {
                "軽トラック": int(request.form.get("truck_cost_軽トラック", 10000)),
                "2tショート": int(request.form.get("truck_cost_2tショート", 30000)),
                "2tロング": int(request.form.get("truck_cost_2tロング", 30000)),
                "2tロングワイド": int(request.form.get("truck_cost_2tロングワイド", 30000)),
            }

            # 設定をセッションに保存
            config = {
                "worker_fee": worker_fee,
                "truck_costs": truck_costs
            }
            save_config(config)
            flash("設定を保存しました！", "success")
        except Exception as e:
            flash(f"エラーが発生しました: {e}", "error")

    # 管理画面を表示
    return render_template("admin.html", config=config)

@app.route("/admin/history.csv")
def download_history_csv():
    history = load_history()

    # CSVデータをメモリに書き出す
    output = []
    headers = ["作成日時", "名前", "金額（税込）", "引越し元住所", "引越し先住所"]
    output.append(headers)

    for item in history:
        data = item["data"]
        row = [
            item["timestamp"],
            item["name"],
            item["total_cost_with_tax"],
            data.get("from_address", ""),
            data.get("to_address", "")
        ]
        output.append(row)

    # 文字列に変換
    def generate():
        for row in output:
            yield ",".join(f'"{str(col)}"' for col in row) + "\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=history.csv"
        }
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render用ポート取得
    app.run(host="0.0.0.0", port=port)
