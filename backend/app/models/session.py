"""
セッションモデル
申請プロセス全体の進捗を管理
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pathlib import Path
import json
import uuid


class StepStatus(str, Enum):
    """ステップの状態"""
    PENDING = "pending"
    RUNNING = "running"
    IN_PROGRESS = "running"  # alias for RUNNING
    COMPLETED = "completed"
    DONE = "completed"  # alias for COMPLETED
    ERROR = "error"


class SessionStatus(str, Enum):
    """セッション全体の状態"""
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    REBUTTAL = "rebuttal"
    COMPLETED = "completed"


class ChainOfThoughtEntry(BaseModel):
    """Chain of Thoughtのエントリ"""
    timestamp: datetime = Field(default_factory=datetime.now)
    step: str
    prompt: Optional[str] = None
    response: Optional[str] = None
    error: Optional[str] = None


class AnalyzeStep(BaseModel):
    """解析ステップ"""
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    chain_of_thought: List[ChainOfThoughtEntry] = Field(default_factory=list)


class ConfirmStep(BaseModel):
    """確認ステップ"""
    status: StepStatus = StepStatus.PENDING
    user_edits: Dict[str, Any] = Field(default_factory=dict)
    confirmed_at: Optional[datetime] = None


class DocumentStatus(BaseModel):
    """書類生成状態"""
    status: StepStatus = StepStatus.PENDING
    path: Optional[str] = None
    error: Optional[str] = None


class GenerateStep(BaseModel):
    """書類生成ステップ"""
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    output_dir: Optional[str] = None  # 出力ディレクトリパス
    generated_documents: List[str] = Field(default_factory=list)  # 生成された書類リスト
    error: Optional[str] = None  # エラーメッセージ
    documents: Dict[str, DocumentStatus] = Field(default_factory=lambda: {
        "application_form": DocumentStatus(),
        "consent_form": DocumentStatus(),
        "implementation_plan": DocumentStatus(),
        "consent_withdrawal": DocumentStatus(),
        "recruitment_notice": DocumentStatus(),
    })


class AgentReviewStatus(BaseModel):
    """エージェントレビュー状態"""
    status: StepStatus = StepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    chain_of_thought: List[ChainOfThoughtEntry] = Field(default_factory=list)


class ReviewStep(BaseModel):
    """レビューステップ"""
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    agents: Dict[str, AgentReviewStatus] = Field(default_factory=lambda: {
        "pi": AgentReviewStatus(),
        "student": AgentReviewStatus(),
        "committee": AgentReviewStatus(),
    })


class SubmitStep(BaseModel):
    """提出ステップ"""
    status: StepStatus = StepStatus.PENDING
    submitted_at: Optional[datetime] = None
    submission_notes: Optional[str] = None


class RebuttalRound(BaseModel):
    """Rebuttalの1ラウンド"""
    round_number: int
    created_at: datetime = Field(default_factory=datetime.now)
    feedback_text: str  # 委員会からの指摘（テキスト入力）
    ai_suggestions: Optional[Dict[str, Any]] = None
    user_response: Optional[str] = None
    status: StepStatus = StepStatus.PENDING
    chain_of_thought: List[ChainOfThoughtEntry] = Field(default_factory=list)


class RebuttalInfo(BaseModel):
    """Rebuttal情報"""
    enabled: bool = False
    rounds: List[RebuttalRound] = Field(default_factory=list)


class ResearchPlanInfo(BaseModel):
    """研究計画情報"""
    raw_input: str = ""
    analyzed_at: Optional[datetime] = None


class SessionSteps(BaseModel):
    """全ステップ"""
    analyze: AnalyzeStep = Field(default_factory=AnalyzeStep)
    confirm: ConfirmStep = Field(default_factory=ConfirmStep)
    generate: GenerateStep = Field(default_factory=GenerateStep)
    review: ReviewStep = Field(default_factory=ReviewStep)
    submit: SubmitStep = Field(default_factory=SubmitStep)


class Session(BaseModel):
    """セッションモデル"""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    status: SessionStatus = SessionStatus.IN_PROGRESS
    
    research_plan: ResearchPlanInfo = Field(default_factory=ResearchPlanInfo)
    steps: SessionSteps = Field(default_factory=SessionSteps)
    rebuttal: RebuttalInfo = Field(default_factory=RebuttalInfo)
    
    # メタデータ
    title: Optional[str] = None  # 研究タイトル（解析後に設定）
    
    def save(self, sessions_dir: Path) -> Path:
        """セッションをファイルに保存"""
        sessions_dir.mkdir(parents=True, exist_ok=True)
        self.updated_at = datetime.now()
        file_path = sessions_dir / f"{self.session_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(mode="json"), f, ensure_ascii=False, indent=2, default=str)
        return file_path
    
    @classmethod
    def load(cls, sessions_dir: Path, session_id: str) -> "Session":
        """セッションをファイルから読み込み"""
        file_path = sessions_dir / f"{session_id}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)
    
    @classmethod
    def list_all(cls, sessions_dir: Path) -> List["Session"]:
        """全セッションを取得"""
        sessions = []
        if sessions_dir.exists():
            for file_path in sessions_dir.glob("*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    sessions.append(cls.model_validate(data))
                except Exception:
                    continue
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)
    
    def add_chain_of_thought(self, step: str, prompt: str = None, response: str = None, error: str = None):
        """Chain of Thoughtエントリを追加"""
        entry = ChainOfThoughtEntry(
            step=step,
            prompt=prompt,
            response=response,
            error=error
        )
        
        if step == "analyze":
            self.steps.analyze.chain_of_thought.append(entry)
        elif step.startswith("review_"):
            agent = step.replace("review_", "")
            if agent in self.steps.review.agents:
                self.steps.review.agents[agent].chain_of_thought.append(entry)
        elif step == "rebuttal" and self.rebuttal.rounds:
            self.rebuttal.rounds[-1].chain_of_thought.append(entry)
    
    def get_current_step(self) -> str:
        """現在のステップを取得"""
        if self.steps.analyze.status != StepStatus.COMPLETED:
            return "analyze"
        if self.steps.confirm.status != StepStatus.COMPLETED:
            return "confirm"
        if self.steps.generate.status != StepStatus.COMPLETED:
            return "generate"
        if self.steps.review.status != StepStatus.COMPLETED:
            return "review"
        if self.steps.submit.status != StepStatus.COMPLETED:
            return "submit"
        if self.rebuttal.enabled:
            return "rebuttal"
        return "completed"
