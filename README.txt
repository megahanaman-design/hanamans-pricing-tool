eBay Pricing Tool
V1.4 fee, duty, and FX audit simulator

Web版 最短起動 Windows
-----------------------

更新後は、repoのフォルダーで次の2操作だけで起動できます。

```bat
git pull
start_profit_web.cmd
```

起動用cmdは、初回だけ ``.venv`` を作成し、必要packageをインストールします。その後、migrationとDjango system checkを実行して、Web版を ``0.0.0.0:8001`` で起動します。``activate`` は不要です。requirements.txtが変わった場合やDjango/python-dotenvをimportできない場合にはpackageを再インストールします。

初回に ``.env`` がなければ ``.env.example`` から自動作成されます。eBay連携を使う場合のみ、作成された ``.env`` を開き、次の3項目を設定してください。未設定でも ``/simple/`` と ``/monthly/`` の画面および利益計算は使用できます。

* ``EBAY_CLIENT_ID``
* ``EBAY_CLIENT_SECRET``
* ``EBAY_RUNAME``

PCでは http://127.0.0.1:8001/ 、月次利益は http://127.0.0.1:8001/monthly/ を開きます。同一LANのスマホやChromebookからは ``http://<PCのIP>:8001/`` を開いてください。SKU Masterはポート8000、Pricing Tool Webはポート8001を使うため、同時に起動できます。

このツールは、国内価格からeBay商品価格USD、利益額、利益率、損益分岐を確認する価格シミュレーターです。
Pokemon PSA Research Toolとは別物です。カード名、URL、在庫管理、eBay検索結果解析は扱いません。

GUIでの使い方:

1. run_gui.vbs を実行する
2. GUIに国内最安値円を入力する
3. 必要に応じて目標粗利率1、目標粗利率2、広告率、為替手動上書きを入力する
4. 「計算する」を押す
5. GUI上で目標粗利率1・2の結果を確認する
6. 詳細確認が必要な場合は監査用Excelを開く

Excelだけで使う場合:

1. input/purchase_input.xlsx に国内最安値円を1件入力する
2. run.bat を実行する
3. output/pricing_result.xlsx の「Simulator」シートを開く
4. 商品価格USDを変更して、還付込み利益額円・還付込み利益率を確認する
5. 必要に応じて仕入価格円やSettingsの設定値も変更する

出力ファイル:

* output/pricing_result.xlsx
  * Simulator
  * InputPrices
  * Settings

価格シミュレーターでできること:

* 商品価格USDを手入力して利益を確認する
* 商品価格USDに応じて関税徴収用送料USDを自動計算する
* 販売価格USD、売上円換算、手数料、送料合計、粗利、還付込み利益をExcel上で再計算する
* 粗利ベース損益分岐価格と還付込み損益分岐価格を別々に確認する
* Settingsシートで、為替・手数料・送料・関税徴収用送料の監査値を確認する

為替:

* 実行時にUSDJPYを自動取得します。
* 原則としてYahoo Finance USDJPY=Xを使用します。
* 取得できない場合はFrankfurter APIを使います。
* それでも取得できない場合は155を使います。
* Settingsシートで取得元、取得日時、ステータスを確認できます。
* 必要に応じて手動上書き為替を入力できます。
* 為替はExcelを開いただけでは自動更新されません。run_gui.vbsまたはrun.batで再実行したタイミングで更新されます。

監査・注意:

* eBay固定手数料USDの初期値は0.40です。
* eBay FVF、海外手数料、広告費はSales Tax込み総販売額ベースで計算します。
* Payoneer手数料率はユーザー環境により異なる可能性があるため、必要に応じてSettingsで調整してください。
* Orange Connex送料は最終的に請求書ベースで確認してください。
* 重要な出品前には、実際のeBay/CPaSS/Payoneer明細と突合してください。

このツールでやらないこと:

* Research Toolとの連携
* カード名管理
* カード番号管理
* URL管理
* 在庫管理
* 仕入先管理
* eBay検索結果解析
* Watch数解析
* 外れ値判定
* 市場判定

Pricing Core purchase-limit API:

* `max_purchase_yen_for_selling_total` は、送料・duty 込みの selling TOTAL 上限から仕入上限を求めます。
* `max_purchase_yen_for_product_price` は、送料・duty を含まない eBay 商品価格から仕入上限を求めます。
* SKU Master の eBay 最安 TOTAL × 1.15 値には、product-price semantic の後者を使用予定です。

デフォルト設定:

* 為替レート: 155
* Sales Tax率: 8.00%
* 荷物分送料円: 3000
* eBay FVF率: 13.25%
* eBay固定手数料USD: 0.40
* 海外手数料率: 1.35%
* 広告率: 2.00%
* Payoneer手数料率: 2.00%
* その他コスト円: 0
* 目標粗利率1: 10.00%
* 目標粗利率2: 20.00%

V1_GUI化_ロジック固定版:

* この版は V1_GUI化_ロジック固定版
* 計算ロジックはこの版で一旦固定
* 今後修正する場合は、必ずバックアップを取ってから行う
* 実運用は run_gui.vbs から起動する
* 実売明細と突合して、手数料率・送料・Payoneer手数料率は必要に応じてSettingsで調整する

GUI中心運用:

* 通常運用はGUI上で完結します。
* Excelは監査用・詳細確認用として出力します。
* 通常起動は run_gui.vbs を使います。
* デバッグ起動は run.bat を使います。
* CMD画面を出したくない場合は run_gui.vbs を使います。
* 国内価格一覧ではなく、国内最安値円を入力します。
* 国内平均価格は使いません。
* 目標利益額入力は廃止しました。
* 目標粗利率1と目標粗利率2を入力します。
* 目標利益率は還付込み利益率ではなく、粗利率ベースで判定します。
* 目標粗利率1の商品価格USDはBest Offer下限の目安です。
* 目標粗利率2の商品価格USDは出品価格の目安です。
* GUIの詳細設定で、海外手数料率、Sales Tax率、荷物分送料円、eBay FVF率を変更できます。
* 詳細設定の%入力は、1.35、8、13.25のように百分率の数字で入力します。
* Payoneer手数料率とeBay固定手数料USDはGUIでは変更せず、従来通りSettings側の値を使います。
* 普段見るべき項目は、使用為替、送料USD、粗利ベース損益分岐、還付込み損益分岐、目標粗利率1の結果、目標粗利率2の結果です。
* 手数料や送料の詳細はSettingsまたは監査用Excelで確認します。
* 計算ロジックはV1_GUI化_ロジック固定版を使用しています。

V1_eBay_Pricing_Tool_完成版:

* この版は V1_eBay_Pricing_Tool_完成版
* 通常起動は run_gui.vbs
* run.bat はデバッグ用
* 計算ロジックはこの版で固定
* 今後修正する場合は、必ずバックアップを取ってから行う
* 実売明細と突合して、手数料率・送料・Payoneer手数料率は必要に応じて見直す

Web版（Phase 1 — CSVなし簡易利益計算）:

既存GUIとは別に、ブラウザから1商品ずつ手入力して利益を計算できます。CSV/Excel/API連携や外部への書き込みは行いません。

Windowsでの手動起動（通常は上記の ``start_profit_web.cmd`` を使用）:

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8001
```

Chromebook Linuxでの起動:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8001
```

どちらもブラウザで http://127.0.0.1:8001/ を開きます。同一LANの別端末から使う場合は、サーバーを起動したPCのIPアドレスとポート8001を指定してください。ポート8000のSKU Masterとは独立しており、同時起動できます。

Web Phase 2: eBay monthly profit
--------------------------------
Run migrations with ``python manage.py migrate`` and open ``/monthly/``. Configure these environment variables (never commit their values):

* ``EBAY_CLIENT_ID``
* ``EBAY_CLIENT_SECRET``
* ``EBAY_RUNAME`` (URLではなく、eBay Developer Portalで発行されたRuName)
* ``DJANGO_SECRET_KEY`` (ローカル用fallbackはありますが、任意の十分長いランダム文字列を設定することを推奨)

Web版のDjango settingsがrepo rootの ``.env`` をpython-dotenvで自動的に読み込みます。OS側ですでに設定された環境変数は ``.env`` より優先されます。``.env`` はGit管理対象外です。秘密値、token、authorization codeをGitへcommitしたり、ログへ貼り付けたりしないでください。

The integration requests only ``sell.fulfillment.readonly`` and only calls the Fulfillment getOrders GET endpoint. It never changes listings, fulfillment, refunds, offers, or any other eBay data. Fulfillment data is commonly limited to recent orders; the UI identifies the 90-day retrieval window. Tokens are never rendered or logged. Phase 2 uses estimated Phase 1 fees; actual fees, promoted listing charges, and partial-refund accounting remain a future Finances API enhancement.

``redirect_uri``としてeBayへ送信する値はcallback URLではなく、eBay Developer Portalで作成した ``EBAY_RUNAME``（RuNameそのもの）です。そのRuNameにHTTPSのAuth Accepted URLを設定する必要があります。``http://127.0.0.1:8001/ebay/callback/`` のようなlocalhost HTTP URLをProductionのAccepted URLとして直接利用することはできません。ngrok、Cloudflare Tunnel、Vercel等の外部公開方法の導入はこのPhaseの対象外です。
