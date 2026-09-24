# gae-dev_appserver-patcher

[English README](README.en.md)

Google Cloud SDKに含まれるGoogle App Engineの`dev_appserver.py`へ、互換パッチを再現可能かつ安全に適用するためのツールです。

パッチ対象ファイルのSHA-256と`app-engine-python`コンポーネントのバージョンを確認し、公式状態または既知の適用済み状態にだけ処理を行います。未知の内容を持つSDKは変更せず、エラーで停止します。

## 公開とサポート範囲について

このプロジェクトはGPT-5.6 SolおよびGPT-6.0 Solによって作成され、人が内容をレビューしています。Googleの承認を受けたものではなく、作者が独自に公開しています。

このパッチ群はGoogle App Engine Standard EnvironmentのGoアプリケーション向けに提供しています。Javaなど、他の言語のアプリケーションでは動作を検証していません。

GoogleがPython 3で完全に動作する`dev_appserver.py`を提供した場合、このプロジェクトの保守を終了します。

## このリポジトリを用意した理由

Google App Engine Standard Environmentの旧来のGoアプリケーションをローカルで動かすには、現在もGoogle Cloud SDK付属の`dev_appserver.py`が必要です。一方、`dev_appserver.py`にはPython 2時代のApp Engine APIと、現在のPython 3、protobuf、gRPC、Datastore Emulatorを橋渡しするコードが含まれており、組み合わせによって次のような問題が発生します。

- Goアプリケーションのビルドや子プロセス起動に失敗する
- Transactional Task Queueの要求をシリアライズできない
- Datastoreのクエリ結果やカーソルを正しく読み取れない
- Datastore Viewerで種類・エンティティの一覧を表示できない
- Cloud Storageへの分割アップロードが空のBlobとして確定される

これらはアプリケーションのコードを変更して回避できる問題ではなく、SDK内の互換処理を補う必要があります。しかし、SDKファイルを手作業で編集すると、別の開発環境へ同じ修正を再現しにくく、SDK更新による上書きや、未検証バージョンへの誤適用にも気付きにくくなります。

そこで、必要な修正をアプリケーションプロジェクトから独立させ、複数のプロジェクトで共有できるパッチ群として管理しています。対象コンポーネントのバージョンと各ファイルのSHA-256を検証することで、「検証済みの公式ファイルへ適用する」「既に適用済みなら何もしない」「未知の状態なら変更せず停止する」という動作を保証します。

## 対象バージョン

- `app-engine-python` 1.9.118
- ビルド番号 `20250822133333`

Cloud SDK全体のバージョンではなく、対象ファイルを提供する`app-engine-python`コンポーネントで判定します。

## 収録パッチ

`manifest.json`にはmacOS/LinuxとWindowsで使用する共通パッチ、`windows-manifest.json`にはWindows固有パッチを定義しています。番号は適用順を示します。

### 001: Goデバッグビルド引数の修正（`go-gcflags`）

Goのデバッグビルドで`-gcflags`の値に引用符そのものが含まれ、Goコンパイラーへ正しい引数が渡らない問題を修正します。`"all=-N -l"`ではなく`all=-N -l`を一つの引数として渡します。

### 002: 公開版protobufの使用（`public-protobuf`）

生成済みgRPCコードが、通常のGoogle Cloud SDK環境には存在しないGoogle内部用protobufモジュールをimportする問題を修正します。import先とランタイムドメインを公開版`google.protobuf`へ置き換えます。

### 003: Task Queue要求のシリアライズ互換性（`taskqueue-protobuf-serialization`）

Transactional Task Queueの要求オブジェクトがPython 3版protobufで`Encode()`を持たず、送信前のシリアライズに失敗する問題を修正します。従来形式では`Encode()`、Python 3版では`SerializeToString()`を使用します。

### 004: Datastoreクエリ応答の変換（`datastore-query-response`）

Datastore Emulatorが返すv4/v1形式の`RunQuery`または`Next`応答を、旧App Engine APIが期待するv3の`QueryResult`として読み取れない問題を修正します。通常のv3応答を維持しつつ、必要な場合だけv4/v1応答を検出・変換します。v4応答が例外なしにv3カーソルとして解釈されるケースも判別します。

### 005: Go子プロセスの環境変数変換（`go-env-strings`、Windowsのみ）

protobufから得た環境変数のキーまたは値が`bytes`や`memoryview`のままWindowsのGo子プロセスへ渡され、`environment can only contain strings`で起動に失敗する問題を修正します。UTF-8でデコードし、文字列として環境へ設定します。

### 006: Datastore Viewerの種類一覧（`datastore-viewer-kinds`）

Datastore Viewerが種類一覧を取得するときに、Datastore Emulatorと互換性のないCompiledQuery経路を使用して失敗する問題を修正します。コンパイルを無効にしたキーのみのクエリで種類名を取得します。

### 007: Datastore Viewerのエンティティ一覧（`datastore-viewer-entities`）

Datastore Viewerのエンティティ一覧でCompiledQueryや`Count()`が必要になり、表示に失敗する問題を修正します。コンパイルを無効にし、要求件数より1件多く取得することで次ページの有無を判定します。そのため、画面上の件数は全件数ではなく、現在のページまでと次ページの存在を示す下限です。

### 008: Cloud Storage分割データの取得（`cloudstorage-direct-chunks`）

Blobstore経由のCloud Storageアップロードを確定するとき、分割データのクエリ列挙に失敗して空のBlobが作られる問題を修正します。開始位置から決まる既知のキーで各分割データを直接取得し、欠落も検出しながら結合します。

## セットアップ

```text
git clone https://github.com/Kazzz/gae-dev_appserver-patcher.git
cd gae-dev_appserver-patcher
```

追加のPythonパッケージは不要です。適用先には、クリーンなGoogle Cloud SDKを用意してください。パッチ適用済みSDKに対して`gcloud components update`は実行せず、SDK更新時はクリーンなSDKから再構築してください。

## パッチの適用

macOS/Linuxでは共通パッチを適用します。

```text
./apply_patches.sh /path/to/google-cloud-sdk
```

Windowsでは共通パッチに続けてWindows固有パッチを適用します。

```text
apply_windows_patches.bat E:\google\google-cloud-sdk
```

`py -3`以外のPythonを使う場合は、実行ファイルの絶対パスを環境変数`GAE_DEV_APPSERVER_PATCH_PYTHON`に設定してください。

```text
set GAE_DEV_APPSERVER_PATCH_PYTHON=E:\Python312\python.exe
apply_windows_patches.bat E:\google\google-cloud-sdk
```

各処理は冪等です。同じコマンドを再実行しても、適用済みファイルは変更しません。

## 適用状態の検証

起動スクリプトから検証を呼び出すと、SDK更新によるパッチ消失を`dev_appserver.py`の起動前に検出できます。

macOS/Linux:

```text
./verify_patches.sh /path/to/google-cloud-sdk
```

Windows:

```text
verify_windows_patches.bat E:\google\google-cloud-sdk
```

Pythonスクリプトを直接呼び出すこともできます。

```text
python3 verify_patches.py --sdk-root /path/to/google-cloud-sdk
python3 verify_patches.py --sdk-root /path/to/google-cloud-sdk --manifest windows-manifest.json
```

## アプリケーションプロジェクトからの利用

複数のプロジェクトから利用する場合は、このリポジトリの配置先を環境変数で渡し、`dev_appserver.py`の起動直前に適用または検証します。

Windowsでは、共通パッチとWindows固有パッチを冪等に適用できます。

```bat
set "GAE_DEV_APPSERVER_PATCHER_ROOT=E:\gae-dev_appserver-patcher"
call "%GAE_DEV_APPSERVER_PATCHER_ROOT%\apply_windows_patches.bat" "%CLOUD_SDK_ROOT%"
if errorlevel 1 exit /b 1
```

macOS/Linuxでは、事前に適用した共通パッチが残っていることを起動ごとに検証できます。

```sh
GAE_DEV_APPSERVER_PATCHER_ROOT=/path/to/gae-dev_appserver-patcher
"$GAE_DEV_APPSERVER_PATCHER_ROOT/verify_patches.sh" "$CLOUD_SDK_ROOT" || exit 1
```

適用・検証に失敗した場合は開発サーバを起動せず、SDKのバージョンとファイル状態を確認してください。

## スモークテスト

適用後は、必要な機能に対応するテストを実行します。

```text
python3 smoke_test_datastore_viewer.py --sdk-root /path/to/google-cloud-sdk
python3 smoke_test_cloudstorage_chunks.py --sdk-root /path/to/google-cloud-sdk
```

Transactional Task QueueとDatastoreクエリ応答のテストには、`dev_appserver`が利用するPython環境と`grpcio`が必要です。

```text
/path/to/dev_appserver/python smoke_test_taskqueue.py --sdk-root /path/to/google-cloud-sdk
/path/to/dev_appserver/python smoke_test_datastore_query.py --sdk-root /path/to/google-cloud-sdk
```

WindowsのGo環境変数変換は次のコマンドで確認します。

```text
py -3 smoke_test_go_env.py --sdk-root E:\google\google-cloud-sdk
```

macOSでDatastore Viewerのテストを行う場合は、SDK管理画面が利用する`cgi`モジュールを含むPython環境（例: `/usr/bin/python3`）を使用してください。Python 3.14では`cgi`が削除されています。

## 既知の注意事項

- 以前に手作業で変更したSDKはハッシュが一致せず、適用を拒否します。クリーンなSDKを別途用意してください。
- Viewerに表示する件数は全件数ではなく、現在のページまでと次ページの存在を示す下限です。
- 修正前に空Blobとして確定したCSVは復旧しません。修正後に再度アップロードしてください。
- 管理画面のTask Queueはスモークテストの対象外です。実環境で別途確認してください。

## SDK更新時の保守

1. 新しいSDKを既存SDKとは別のディレクトリへ展開します。
2. `apply_patches.py`を実行し、未検証バージョンとして停止することを確認します。
3. 公式版との差分と上流の修正状況を調査します。
4. 不要になったパッチを削除するか、新しい公式ファイルを基準にマニフェストのSHA-256とパッチを更新します。
5. 適用、検証、関連スモークテストを行ってから利用先を切り替えます。

パッチファイルは単一ハンクのunified diffです。`apply_patches.py`は、対象文字列がちょうど1件存在し、適用後のSHA-256がマニフェストと一致する場合のみ書き込みます。
