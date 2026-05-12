## ダウンロード

| OS | ファイル |
|---|---|
| Windows x64 | `EthicalReviewHacker_*_x64_en-US.msi` または `*_x64-setup.exe` |
| macOS Apple Silicon (M1/M2/M3/M4) | `EthicalReviewHacker_*_aarch64.dmg` |
| macOS Intel | `EthicalReviewHacker_*_x64.dmg` |

## ⚠️ macOS をお使いの方へ

このアプリは Apple のコード署名・公証を行っていないため、初回起動時に Gatekeeper が「壊れている」「開発元を確認できない」と表示します。以下のいずれかで回避できます。

**方法 A (推奨): ターミナルで quarantine 属性を外す**

```bash
xattr -dr com.apple.quarantine /Applications/EthicalReviewHacker.app
```

**方法 B**: Finder で右クリック → 「開く」を 2 回繰り返す

## ⚠️ Windows をお使いの方へ

SmartScreen が「PC を保護しました」と表示する場合は、「詳細情報」 → 「実行」 で起動できます。

## 初回設定

起動後、右上 ⚙ から **Gemini API Key** または **OpenAI API Key** を保存してください。
