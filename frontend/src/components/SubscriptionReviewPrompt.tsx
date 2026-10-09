import { useState } from 'react';
import { toast } from 'react-toastify';
import { Button } from './common/Button';
import { Textarea } from './common/Input';
import './SubscriptionReviewPrompt.css';

interface SubscriptionReviewPromptProps {
  prompt: string;
}

export function SubscriptionReviewPrompt({ prompt }: SubscriptionReviewPromptProps) {
  const [copied, setCopied] = useState(false);

  const copyPrompt = async () => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(prompt);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = prompt;
        textarea.style.position = 'fixed';
        textarea.style.left = '-9999px';
        document.body.appendChild(textarea);
        textarea.select();
        const copiedSuccessfully = document.execCommand('copy');
        textarea.remove();
        if (!copiedSuccessfully) throw new Error('Clipboard copy failed');
      }
      setCopied(true);
      toast.success('レビュー用プロンプトをコピーしました');
    } catch (error) {
      console.error('Review prompt copy failed:', error);
      toast.error('コピーできませんでした。テキスト欄から手動でコピーしてください。');
    }
  };

  return (
    <section className="subscription-review-prompt">
      <h3>ChatGPTサブスクで書類をレビュー</h3>
      <p>
        生成したZIPを展開し、レビューしたい書類をChatGPTに添付してから、下のプロンプトを貼り付けてください。
        このレビューはChatGPT上で手動実行するため、アプリのAPIキーやAPI利用料は使いません。
        書類の生成には、これまでどおり設定したLLM APIを使用します。
      </p>
      <Textarea
        aria-label="ChatGPTサブスク用レビュー・プロンプト"
        className="subscription-review-prompt-textarea"
        value={prompt}
        readOnly
        rows={18}
      />
      <Button variant="secondary" onClick={copyPrompt}>
        {copied ? '✅ コピー済み' : '📋 レビュー用プロンプトをコピー'}
      </Button>
    </section>
  );
}
