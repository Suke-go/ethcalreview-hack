import type { AnalysisResult, Investigator, PresetBundle } from '../types';

export interface SubscriptionReviewPromptInput {
  researchPlan: string;
  analysis: AnalysisResult;
  investigator: Investigator;
  presets: PresetBundle | null;
  investigatorPresetId?: string;
  facilityName: string;
  subInvestigators: { affiliation: string; position: string; name: string }[];
  withdrawalPeriodDays: number | null;
  hasCompensation: boolean;
  noCompensationReason?: string;
  storageLocation: string;
  dataManager: string;
  managementMethod: string;
  disposalMethod: string;
}

const valueOrPlaceholder = (value: string | undefined): string => value?.trim() || '未入力';

export function buildSubscriptionReviewPrompt(input: SubscriptionReviewPromptInput): string {
  const selectedInvestigator = input.presets?.investigator_presets.find(
    (preset) => preset.id === input.investigatorPresetId,
  );
  const investigatorName = selectedInvestigator?.name || input.investigator.name;
  const withdrawalDeadline = input.withdrawalPeriodDays == null
    ? '研究成果の公表前まで'
    : `同意書署名日から${input.withdrawalPeriodDays}日以内`;
  const compensation = input.hasCompensation
    ? '健康被害に対する補償を行う設定です。保険による補償の説明が書類間で一致しているか確認してください。'
    : `健康被害に対する補償を行わない設定です。理由: ${valueOrPlaceholder(input.noCompensationReason)}`;
  const subInvestigators = input.subInvestigators.length
    ? input.subInvestigators.map((person) => `${person.name}（${person.affiliation}・${person.position}）`).join('、')
    : 'なし';

  return `あなたは、大学の研究倫理審査書類を点検するレビュアーです。添付された書類一式を読み、書類の内容と相互の整合性を確認してください。これは正式な倫理審査の代替ではなく、提出前の確認です。添付ファイルを読めない場合は推測せず、その旨を最初に伝えてください。

## 研究計画の情報
- 研究課題名: ${valueOrPlaceholder(input.analysis.research_title)}
- 研究目的: ${valueOrPlaceholder(input.analysis.research_purpose)}
- 研究方法: ${valueOrPlaceholder(input.analysis.research_method)}
- 実験参加者: ${valueOrPlaceholder(input.analysis.target_participants)}
- 予定人数: ${input.analysis.participant_count}
- 実施場所: ${valueOrPlaceholder(input.facilityName)}
- 実施責任者: ${valueOrPlaceholder(investigatorName)}
- 実施分担者: ${subInvestigators}
- データ管理責任者: ${valueOrPlaceholder(input.dataManager)}
- データ管理場所: ${valueOrPlaceholder(input.storageLocation)}
- 撤回期限の設定: ${withdrawalDeadline}
- 補償: ${compensation}
- データ管理方法: ${valueOrPlaceholder(input.managementMethod)}
- データ処分方法: ${valueOrPlaceholder(input.disposalMethod)}

## 原資料の研究計画
以下は書類の記載内容と照合するための原資料です。書類にない情報を補わず、原資料との食い違いを指摘してください。
<研究計画>
${valueOrPlaceholder(input.researchPlan)}
</研究計画>

## レビューの進め方
次の2つの観点を分けて点検し、その後に指摘を統合してください。実際に別々のAIが動作したかのようには説明せず、1つのレビュー内での2つの観点として扱ってください。

### 観点A: 書類間の整合性
- 研究課題名、研究目的・方法、対象者、予定人数、期間、場所、責任者・分担者、謝金が書類間で一致しているか。
- 「実験参加者」「実験実施者」「実施責任者」「実施分担者」の役割が区別され、呼び名が書類間で統一されているか。
- 参加の中止と、取得済みデータ提供への同意撤回が別の事項として説明されているか。
- データ提供の同意撤回期限が「${withdrawalDeadline}」で統一され、起算日が明記されているか。参加自体はいつでも中止できる説明と混同されていないか。
- 既に仮名加工され、集計・公表されたデータは個別に特定して削除できない旨が、関係書類で同じ意味に説明されているか。
- 補償の有無・理由・保険の説明が書類間で一致しているか。
- 管理場所・管理方法・処分方法が一致し、保管媒体を初期化した後、復元できないよう物理的に破壊して処分する説明があるか。

### 観点B: 参加者への説明と審査上の確認
- 参加が自由意思であり、不参加や途中中止による不利益がないと分かるか。
- 研究内容、所要時間、手順、負担・リスクと対策、個人情報・データの扱い、問い合わせ先が具体的で分かりやすいか。
- 同意取得・撤回手続きと、撤回後に削除できるデータの範囲が現実的かつ明確か。
- 倫理審査書類として不足している説明、曖昧な表現、矛盾、誤記がないか。

## 出力形式
1. 全体評価（提出前に直すべき重大な問題の有無）
2. 観点A・観点Bごとの指摘。各指摘は「重要度（重大・要修正・軽微）」「書類名と該当箇所」「現在の記載（短い引用）」「問題点」「修正案」を含める。
3. 書類間の表記・数値の比較表。問題がない項目も一致を確認したことが分かるようにする。
4. 情報不足で判断できない項目。事実を創作しない。
5. 指摘がない場合は「確認できる範囲で重大な不整合は見つかりませんでした」と明記する。

添付資料に書かれていない事実や大学独自の規程を推測で断定しないでください。修正案は、書類にそのまま反映できる日本語で示してください。`;
}
