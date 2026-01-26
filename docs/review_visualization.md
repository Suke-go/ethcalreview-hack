# Multi-Agent Review Visualization

## 概要

査読者・AI・研究者の三者間のやり取りをタイムライン形式で可視化するコンポーネント。

## 機能

### 1. タイムライン表示

- **ラウンド管理**: 各査読ラウンドを時系列で表示
- **エージェント識別**: 査読者 👨‍🔬 / AI 🤖 / 研究者 👨‍💼 を色とアイコンで区別
- **自動スクロール**: 新しいラウンドが追加されると自動的に最下部までスクロール

### 2. メッセージタイプ

#### 査読者コメント（黄色）
- 査読者からの指摘事項を表示
- フォーマット: 生のフィードバックテキスト

#### AI提案（青色）
- AIが生成した改善提案を表示
- 提案タイプ:
  - ➕ 追加 (addition)
  - ✏️ 修正 (modification)
  - 🗑️ 削除 (deletion)
  - 💡 説明 (clarification)
- **信頼度スコア**: 各提案の信頼度を0-100%で表示
- **折りたたみ可能**: 提案詳細の表示/非表示を切り替え

#### 研究者返答（緑色）
- 研究者の最終的な回答文を表示

### 3. リアルタイム更新

- 3秒ごとに `/api/rebuttal/{sessionId}/rounds` エンドポイントをポーリング
- 新しいラウンドが追加されると自動的に表示更新

## API連携

### エンドポイント

```typescript
GET /api/rebuttal/{sessionId}/rounds
```

**Response**:
```json
[
  {
    "roundNumber": 1,
    "feedbackText": "実験時間が不明確です",
    "status": "completed",
    "createdAt": "2026-01-26T20:00:00",
    "hasSuggestions": true,
    "suggestions": [
      {
        "id": 1,
        "type": "modification",
        "targetSection": "methodology",
        "suggestedText": "実験時間は約60分です",
        "confidence": 0.92,
        "rationale": "所要時間の明示が必要"
      }
    ],
    "responseDraft": "ご指摘ありがとうございます。実験時間は約60分です。"
  }
]
```

## 使用方法

### 基本的な使い方

```tsx
import ReviewVisualization from './components/ReviewVisualization';

function App() {
  const [showReview, setShowReview] = useState(false);
  const sessionId = "abc-123-def";

  return (
    <div>
      <button onClick={() => setShowReview(true)}>
        レビュー履歴を表示
      </button>

      {showReview && (
        <ReviewVisualization
          sessionId={sessionId}
          onClose={() => setShowReview(false)}
        />
      )}
    </div>
  );
}
```

### モーダルとして使う

```tsx
import Modal from './components/Modal';
import ReviewVisualization from './components/ReviewVisualization';

<Modal isOpen={showReview} onClose={() => setShowReview(false)}>
  <ReviewVisualization sessionId={sessionId} />
</Modal>
```

## スタイリング

### カラーコード

- **Header Gradient**: `linear-gradient(135deg, #667eea 0%, #764ba2 100%)`
- **査読者**: `#fff3cd` (黄色背景)
- **AI**: `#e7f3ff` (青色背景)
- **研究者**: `#d4edda` (緑色背景)

### カスタマイズ

`ReviewVisualization.css`を編集してスタイルを変更:

```css
.reviewer-message {
    background: #your-color;
    border-left: 4px solid #your-border-color;
}
```

## 拡張性

### カスタムフィルター

特定のラウンドのみを表示:

```tsx
const filteredRounds = rounds.filter(r => r.status === 'completed');
```

### エクスポート機能の追加

```tsx
const exportToJSON = () => {
  const dataStr = JSON.stringify(rounds, null, 2);
  const blob = new Blob([dataStr], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `review-${sessionId}.json`;
  a.click();
};
```

## パフォーマンス

- 仮想スクロール（100ラウンド以上の場合に推奨）:
  ```bash
  npm install react-window
  ```

- メモ化:
  ```tsx
  const MemoizedRoundDisplay = React.memo(ReviewRoundDisplay);
  ```

## トラブルシューティング

### ラウンドが表示されない

1. ネットワークタブで `/api/rebuttal/{sessionId}/rounds` のレスポンスを確認
2. Console で `rounds` state の内容を確認

```tsx
useEffect(() => {
  console.log('Rounds:', rounds);
}, [rounds]);
```

### スクロールが動作しない

`scrollRef.current` が null でないか確認:

```tsx
console.log('Scroll ref:', scrollRef.current);
```
