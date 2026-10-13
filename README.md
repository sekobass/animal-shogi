# codex-test
Codexで使うPythonコード置き場など

## Animal Shogi
動物将棋改良版


```
python animal_shogi.py
```

## 強化AI版（Windows / Chromebook）

同じ `animal_shogi_engine.py` のルール・AIをデスクトップ版とブラウザ版で使用します。

### Windows

GitHub Actions の **Build and test** にある `animal-shogi-windows` をダウンロードし、ZIP内の `AnimalShogi.exe` を実行してください。Pythonのインストールは不要です。Windows x64向けです。未署名のためSmartScreen等が警告する場合があります。配布元とファイルを確認してください。

ローカルビルドはWindows上で実行します（LinuxからWindows EXEは生成しません）。

```powershell
python -m pip install pyinstaller==6.16.0
python -m PyInstaller --noconfirm --clean --onefile --windowed --name AnimalShogi animal_shogi_strong.py
```

### Chromebook（ブラウザ）

GitHub PagesのサイトをChromeで開いてください。Linux環境は不要です。初回・再読み込み時にPyodideをCDNから読み込むためインターネット接続が必要です。先手／後手を選び、駒と移動先をクリックします。

サイトの公開にはリポジトリの Settings → Pages → Source を **GitHub Actions** に設定し、Actionsの **Publish browser game** を実行します。非公開リポジトリからのPages公開には対応プランが必要です。ゲームとルール・AIコードはサイト上で公開されます。リポジトリの公開範囲を変更する必要はありません。

または **Build and test** の `animal-shogi-browser` にある `animal-shogi.html` をダウンロードしてChromeで開けます。

```bash
python tools/build_browser.py
python -m unittest discover -s tests -v
```

GUIテストには画面表示先が必要です。Linuxでは `xvfb-run -a python -m unittest discover -s tests -v` で実行できます。

### 強化AIの探索

Windows／ブラウザ共通で、最大10手の反復深化・αβ探索を使用します。1手あたり20,000探索ノードで打ち切り、最後に完了した深さの最善手を返します。捕獲・トライ・成りを優先し、読みの末端でも直後の捕獲とトライを確認します。千日手の履歴は探索分岐ごとに保持し、局面だけを使った誤った評価キャッシュは使いません。

`python tools/benchmark_ai.py` で、以前の3手読みAI（コミット027608d）と6局面・先後入れ替えの12対局を比較できます。今回の固定条件では新AIの12勝0敗0分でした。これは完全解析や人間に対する無敗を保証する結果ではありません。
