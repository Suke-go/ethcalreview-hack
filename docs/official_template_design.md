# 公式様式テンプレート設計

## 目的

`docs/Format` に置かれた公式様式を、文書生成の正本テンプレートとして扱うための設計を定義する。ここでいう正本とは、余白、ページサイズ、段落順、表、署名欄、受付日・承認日欄、固定見出しを維持する対象であり、公式様式内に事前記入されている研究内容や氏名などの旧値は本文生成の参考にしない。

LLM は本文候補の生成だけを担当する。docx のレイアウト、表、署名欄、チェック欄、段落配置は固定処理で作る。

## 基本原則

- 公式 docx をゼロから再現しない。
- 公式 docx の段落順、表構造、署名欄、日付欄、受付日・承認日欄を維持する。
- 旧値文字列を置換キーにしない。
- 見出しや固定ラベルをアンカーとして使い、アンカーからの相対位置または管理されたフィールド範囲に値を入れる。
- チェックボックスは `■` / `□` 文字として扱う。
- LLM 生成文は一度 structured context に格納し、docx への反映は deterministic renderer が行う。
- 生成後に未置換値、旧値混入、文書間不整合を検査する。

## ディレクトリ構成案

```text
backend/
  templates/
    official/
      01-1_研究倫理審査申請書.docx
      03_同意書.docx
      04_同意撤回書.docx
      謝金単価の根拠.docx
      実験参加者リスト.xlsx
      manifest.json
    working/
      README.md
  presets/
    submission_presets.json
    investigator_presets.json
    budget_presets.json
    room_presets.json
docs/
  Format/
    ...
```

`docs/Format` は取り込み元、`backend/templates/official` は生成で使う正本テンプレート置き場とする。正本テンプレートには、事前記入値を参考にした生成ロジックを持たせない。

## Template Manifest

各テンプレートには `manifest.json` で構造情報と検証条件を持たせる。

```json
{
  "version": "2026-05-02",
  "templates": {
    "application_form": {
      "file": "01-1_研究倫理審査申請書.docx",
      "kind": "docx",
      "layout_lock": true,
      "required_anchors": [
        "研　究　倫　理　審　査　申　請　書",
        "１　課題名",
        "３　実施分担者",
        "１３　添付書類",
        "１４　実施責任者の問い合わせ先"
      ],
      "renderer": "application_form_v1"
    },
    "consent_form": {
      "file": "03_同意書.docx",
      "kind": "docx",
      "layout_lock": true,
      "required_anchors": [
        "同　　意　　書",
        "研究や実験に協力した結果",
        "研究の概要について",
        "③　個人情報の保護について"
      ],
      "renderer": "consent_form_v1"
    },
    "consent_withdrawal": {
      "file": "04_同意撤回書.docx",
      "kind": "docx",
      "layout_lock": true,
      "required_anchors": [
        "同　　意　　撤　　回　　書",
        "研究や実験に協力することを撤回した結果"
      ],
      "renderer": "consent_withdrawal_v1"
    }
  }
}
```

`required_anchors` は旧値ではなく、公式様式の固定ラベルだけを指定する。生成前後でアンカーが消えていないことを検査する。

## 共通 Context

すべての文書は以下の正規化済み context を参照する。フロントエンドの camelCase、バックエンドの snake_case、プリセット値、手動修正値を直接テンプレートへ渡さない。

```json
{
  "research": {
    "title": "",
    "background": "",
    "purpose": "",
    "significance": "",
    "method": "",
    "period_start_text": "研究倫理委員会承認後",
    "period_end_text": ""
  },
  "submission": {
    "preset_id": "",
    "recipient": "",
    "committee_name": "",
    "office_name": "",
    "office_tel": ""
  },
  "principal_investigator": {
    "preset_id": "",
    "affiliation": "",
    "position": "",
    "name": "",
    "email": "",
    "tel": ""
  },
  "conductors": [
    {
      "affiliation": "",
      "position": "",
      "name": "",
      "tel": ""
    }
  ],
  "domain_head": {
    "domain": "",
    "name": ""
  },
  "facility": {
    "type": "single",
    "rooms": [],
    "external_facility": "",
    "tsukuba_role": ""
  },
  "funding": {
    "source": "",
    "pi_name": "",
    "project_title": "",
    "project_code": ""
  },
  "reward": {
    "enabled": true,
    "amount": null,
    "unit": "hour",
    "type": "",
    "rationale": "",
    "estimated_minutes": null,
    "estimated_participants": null,
    "total_amount": null
  },
  "participants": {
    "criteria": "",
    "inclusion_criteria": [],
    "exclusion_criteria": [],
    "count": null,
    "count_rationale": "",
    "recruitment_method": ""
  },
  "procedures": [],
  "risks": [],
  "risk_countermeasures": [],
  "recording": {
    "enabled": false,
    "types": [],
    "public_release": false
  },
  "data": {
    "types": [],
    "retention_period": "当該論文等の発表後10年間",
    "anonymization_enabled": true,
    "correspondence_table_enabled": true,
    "storage_location": "",
    "manager": "",
    "management_method": "",
    "disposal_method": "",
    "disclosure_to_participant": true,
    "disclosure_to_proxy": false
  },
  "consent": {
    "target_age": "18歳以上",
    "can_confirm_will": true,
    "method": "文書を添えて口頭にて説明する",
    "withdrawal_deadline_text": "同意書署名の日から90日後"
  },
  "publication": {
    "enabled": true,
    "methods": [],
    "identifiable_data_disclosed": false
  },
  "attachments": {
    "conflict_of_interest_form": true,
    "implementation_plan": true,
    "explanation_document": true,
    "consent_form": true,
    "consent_withdrawal_form": true,
    "video_consent_form": false,
    "other": ""
  }
}
```

## プリセット Context への反映

プリセットは context の初期値を埋めるために使う。プリセット値は常に手動入力で上書き可能とする。

反映順:

1. アプリ同梱デフォルト
2. ユーザー編集済みプリセット
3. 選択された提出先プリセット
4. 選択された責任者プリセット
5. 研究ごとのフォーム入力
6. 研究ごとの手動上書き

同一フィールドに値がある場合は、後段を優先する。生成済みセッションには、最終 context と使用プリセット ID/version を保存する。

## 申請書テンプレート設計

対象: `01-1_研究倫理審査申請書_260422.docx`（2026/04/22 改訂・現行公式様式）

> **改訂メモ（2026/05）**: 大学が申請書様式を 2026/04/22 付で `1.x / 2.x / 3.x …` の章番号体系へ改訂した。
> 旧 `１〜１４` 番号体系の様式（`01-1.研究倫理審査申請書.docx`）は退役。本ドキュメント旧版では
> 「`1.1` 形式は独自様式として採用しない」としていたが、その `1.x` 構成が**現行の公式様式そのもの**に
> なったため方針を反転し、260422 を正本とする。レンダラは `render_application_form`
> （manifest renderer = `application_form_v2_260422`）。

### アンカーと差し込み（260422）

全段落構成（表なし）。章ラベルをアンカーに、値段落・チェックボックス（■/□）を上書きする。

| アンカー | 差し込み対象 | 更新方法 |
| --- | --- | --- |
| `別記様式第１` | 申請日 | 次段落を令和日付に差し替え |
| `申請者（実施責任者又は指導教員）` | 宛名・所属・職名・氏名 | 前段落（宛名）と後続 3 段落を更新 |
| `課題名` | 課題名 | `1.1　課題名　{title}` に更新 |
| `研究倫理委員会承認後` | 研究期間 | 1.2 の期間段落を更新 |
| `新規申請` / `変更申請` | 1.3 申請種別 | `■`/`□` を更新 |
| `今回の申請に類似した内容` | 1.3 類似申請有無 | 後続の `無`/`有` を更新 |
| `職名等`（1.4 見出し行） | 実施分担者 | 見出し直後に分担者行を挿入（責任者と別人のみ） |
| `域名・域長名` | 1.5 関係組織の長 | 段落を更新 |
| `筑波大学単独施設での研究` ほか | 1.6 実施施設 a/b/c・施設名 | チェックと施設名を更新 |
| `資金の種類と、研究代表者` | 1.7 費用の出所 | 見出し直後に資金情報を挿入 |
| `1.8　謝金` | 謝金有無・単価 | チェックと単価を更新 |
| `1.9　利益相反` | 利益相反有無 | チェックを更新 |
| `臨床研究ではない` / `介入（` / `侵襲性（` | 1.11 研究区分 | チェックを更新 |
| `研究対象者への健康被害の補償` | 1.12 補償 | 有無・保険種別チェックを更新 |
| `データの種類（記入）` / `2.6` 各項目 | 2 取得データ・管理 | 種類・保管期間・管理場所/責任者/方法/処分・匿名化を更新 |
| `2.7` 開示 / `2.8` 公開 | 開示・公開可否 | チェックを更新 |
| `人数の見積もり` / `3.4 選択基準` / `3.5 募集方法` | 3 実験対象者 | 人数・根拠・選択/除外基準・募集方法を更新 |
| `研究に伴う危害発生の可能性・安全性` / `4.x` | 4 安全性・侵襲 | リスク/回避策・侵襲チェックを更新 |
| `インフォームド・コンセントを得る` / `5.2` | 5 IC | 取得方法・対象者属性・説明方法を更新 |
| `添付書類` 各行 | 7 添付書類 | `attachments` からチェック更新 |
| `実施責任者の問い合わせ先` | 8 連絡先 | 所属・職名・氏名・内線・メールを更新 |

### 禁止事項

- 公式様式（260422）の段落順・固定文・チェック欄を崩さない。
- 旧研究名や旧科研費名を置換元として使わない（`OLD_VALUE_DENYLIST` で検査）。
- 任意記入欄（`（記入）`）にデータが無い場合は無理に埋めず、様式のプロンプトを残す。

## 同意書テンプレート設計

対象: `03_同意書 1.docx`

同意本文の主要部分は 1 セル表内にあるため、表セル内段落も通常段落と同じように走査する。

### アンカーと差し込み

| アンカー | 差し込み対象 | 更新方法 |
| --- | --- | --- |
| `同　　意　　書` | 固定 | 維持 |
| `筑波大学...系長　殿` | 宛名 | `submission.recipient` から更新 |
| `私は，` または `私は、` で始まる同意本文 | 課題名・説明対象 | 研究内容に応じた固定文テンプレートで再生成 |
| `「課題名：` を含む説明取得文 | 課題名 | 課題名だけ更新 |
| `実施責任者　所　属` | 責任者所属 | 責任者プリセットから更新 |
| `氏　名` の責任者欄 | 責任者氏名 | 責任者プリセットから更新 |
| `データ提供の同意撤回の期限` | 撤回期限 | `consent.withdrawal_deadline_text` に統一 |
| `研究や実験に協力した結果` | 連絡先 | 後続の分担者・責任者・事務局を更新 |
| `研究の概要について` | 参加者条件、目的、意義、方法、所要時間、リスク、謝礼 | LLM 生成済み本文を差し込み |
| `③　個人情報の保護について` | 匿名化、管理方法、任意性 | context から固定文生成 |

### 裏面（別紙「研究の概要について」）の流し込み — 実装済み

裏面 ①②③ は `render_consent_back_side` が `build_consent_overview_sections(context)` の返す
**順序付きセクションリスト**を元に流し込む。各セクションは `{anchor, mode, lines}` を持ち、
`mode="insert_after"`（公式ラベル直後に本文段落を挿入）/ `mode="replace_next"`（テンプレに残る
サンプル本文段落を上書き）で適用する。テンプレ `03_同意書 1.docx` 裏面は本文（body）の独立段落で、
`[参加者条件]` `[目的]` `[意義]` `[方法]` `[所要時間]` `[考えられるリスク]` `[謝礼]` のラベル直後に内容を挿入する。

**拡張方針**: 裏面に載せる内容は同意書固有の項目に限らない。`build_consent_overview_sections` は
申請書・実施計画書と**同じ正規化 context** を参照し、現状で以下を載せる。項目を追加・並べ替えるには
このビルダのリストを編集するだけでよい（レンダラ本体の変更不要）。

- 申請書/実施計画書と共通の研究内容：`research.purpose` / `research.significance` / `research.method`
- 実験手順：`procedures`（`[方法]` 直下に `【実験手順】` 番号付きで挿入）
- ② 必要性・リスク・安全性・危険回避：`participants.count_rationale` / `risks` / `risk_countermeasures`、
  および将来拡張用の補償・安全対策（`safety.measures` / `safety.compensation_text`）
- ③ 個人情報保護：`data.*`（匿名化・管理場所/責任者/方法・処分・保存期間）と `consent.withdrawal_deadline_text`

`(2) データの管理方法` `(3) 研究参加の任意性` はテンプレに前任研究のサンプル本文が残っているため
`replace_next` で必ず上書きし、旧サンプル文を出力に残さない。

### 記録媒体に応じた文言

`recording.enabled = false` の場合、同意本文に `ビデオ録画を含めた` を残さない。

例:

- 記録あり: `ビデオ録画を含めた個人情報の保護`
- 記録なし: `個人情報の保護およびデータ管理`

## 同意撤回書テンプレート設計

対象: `04_同意撤回書 1.docx`

### アンカーと差し込み

| アンカー | 差し込み対象 | 更新方法 |
| --- | --- | --- |
| `同　　意　　撤　　回　　書` | 固定 | 維持 |
| `筑波大学...系長　殿` | 宛名 | `submission.recipient` から更新 |
| `私は、` または `私は，` で始まる撤回本文 | 課題名 | 研究タイトル入り固定文で更新 |
| `上記のとおり同意撤回の申し出を受けました` | 課題名 | 研究タイトル入り固定文で更新 |
| `実験責任者　所　属` | 責任者所属 | 責任者プリセットから更新 |
| `氏　名` の責任者欄 | 責任者氏名 | 責任者プリセットから更新 |
| `研究や実験に協力することを撤回した結果` | 連絡先 | 分担者・責任者・事務局を更新 |

### 禁止事項

- 課題名 2 箇所の片方だけを更新しない。
- 旧課題名を置換元にしない。
- 署名欄を崩さない。

## 謝金根拠テンプレート設計

対象: `(1)_謝金単価の根拠について（様式）.docx`

この様式は段落のみで構成されている。見出し段落の直後に値段落を追加または更新する。

| アンカー | 差し込み対象 |
| --- | --- |
| `本学教員` | 責任者所属・氏名 |
| `研究課題名` | 課題名 |
| `経費` | 予算種別、研究代表者、課題番号 |
| `【場所】` | 実施場所 |
| `【期間】` | 実施期間 |
| `【謝金対象者】` | 対象者条件・人数 |
| `【内容等】` | 実験内容・所要時間 |
| `謝金支出案` | 単価、時間、人数、総額、算出根拠 |

## 参加者リストテンプレート設計

対象: `実験参加者リスト.xlsx`

`公式` シートを正本として使う。`Sheet1` にサンプル個人情報があるため、生成テンプレート化時に削除または空欄化する。

生成ルール:

- 入力参加者がない場合、空の名簿を出力する。
- 入力参加者がある場合、No.、氏名、所属、メール、住所、実験日、謝礼形式、金額を埋める。
- サンプル氏名・メールが残っていれば validation error にする。

## LLM 生成セクション

LLM が生成してよいのは、以下の本文候補だけとする。

- 実施計画書の各章本文
- 同意書裏面の `参加者条件`
- `目的`
- `意義`
- `方法`
- `所要時間`
- `考えられるリスク`
- `謝礼`
- `研究対象者の必要性，研究への参加におけるリスクと安全性，危険回避の方法`

LLM が生成してはいけないもの:

- docx レイアウト
- 署名欄
- 日付欄
- 表構造
- チェック欄
- 宛名
- TEL やメールなどのプリセット値
- 旧値を参考にした研究本文

## Validation 設計

生成後、全文抽出して以下を検査する。

### 未置換検査

- `{{`
- `{%`
- `temp`
- `affliation`
- `name`
- `TODO`
- `（記入）`

### 旧値混入検査

旧研究内容やサンプル参加者情報は denylist として管理する。ただし責任者プリセットとして明示管理された氏名・TEL は denylist に入れない。

検査対象例:

- 旧研究課題名
- 旧実験内容固有語
- サンプル参加者氏名
- サンプル参加者メール
- 公式様式に残っていた別研究の課題名

### 文書間整合性検査

- 課題名が全 docx で一致する。
- 撤回期限が申請書、同意書、実施計画書で一致する。
- 謝金額と謝金形式が申請書、同意書、実施計画書、謝金根拠で一致する。
- 責任者氏名、所属、TEL が申請書、同意書、撤回書で一致する。
- 提出先・事務局 TEL が同意書と撤回書で一致する。

## 参考文献

- Microsoft Learn, Structure of a WordprocessingML document: https://learn.microsoft.com/en-us/office/open-xml/word/structure-of-a-wordprocessingml-document
- python-docx documentation: https://python-docx.readthedocs.io/en/latest/
- python-docx-template documentation: https://docxtpl.readthedocs.io/en/latest/
- Jinja template documentation: https://jinja.palletsprojects.com/en/stable/templates/
- openpyxl tutorial: https://openpyxl.readthedocs.io/en/stable/tutorial.html
- docx2python: https://github.com/ShayHill/docx2python
