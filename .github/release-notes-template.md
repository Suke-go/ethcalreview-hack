## 🚨 必ず必ず必ず必ず必ず必ず必ず必ず必ず必ず必ず必ず必ず レビューしてください 🚨

本ツールが出力する申請書類は **AI による下書き** です。レビューせずにそのまま倫理審査委員会へ提出することは、絶対に避けてください。

- レビューを怠ると、**審査ご担当の先生方を混乱させ**、本来は短く済む確認が長引き、**結果として審査がより時間を要する** ことに繋がりかねません。
- 不正確な記載が残ったまま審査・実施に進むと、最悪のケースでは **研究不正** に発展する恐れもあります。
- 倫理審査申請書を書く過程は、本来 **自分の研究計画を自分で見直す大切な機会** です。AI 生成中・レビュー中に気付くことも多いはずです。その気付きを大切にしてください。

生成内容は **責任を持って精読・修正** の上ご提出いただきますよう、何卒よろしくお願いいたします。

---

## ダウンロード

| OS | ファイル |
|---|---|
| Windows x64 | `EthicalReviewHacker_*_x64_en-US.msi` または `*_x64-setup.exe` |
| macOS (Apple Silicon: M1/M2/M3/M4) | `EthicalReviewHacker_*_aarch64.dmg` |

> macOS Intel 版はバイナリ配布していません。Intel Mac で動かす場合はソースから `bash scripts/stage-sidecar.sh && npm --prefix frontend exec tauri build` をご利用ください。

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
