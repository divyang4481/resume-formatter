export type AgentSessionStatus = "idle" | "uploading" | "processing" | "waiting_for_user" | "review" | "completed" | "failed";

export type AgentMessageRole = "assistant" | "user" | "system";
export type AgentMessageType = "text" | "status" | "question" | "warning" | "result";

export type AgentMessage = {
  id: string;
  role: AgentMessageRole;
  type: AgentMessageType;
  content: string;
  timestamp: string;
};

export type AgentActionType =
  | "upload_document"
  | "select_template"
  | "confirm_pii_policy"
  | "review_extraction"
  | "submit_correction"
  | "rerun_job"
  | "download_output"
  | "start_over";

export type AgentAction = {
  id: string;
  type: AgentActionType;
  label: string;
  payload?: Record<string, unknown>;
};

export type AgentQuestionType = "single_select" | "multi_select" | "text" | "confirmation";

export type AgentQuestion = {
  id: string;
  questionType: AgentQuestionType;
  title: string;
  description?: string;
  options?: { label: string; value: string }[];
  required: boolean;
};

export type AgentArtifacts = {
  fileUrl?: string;
  extractedData?: Record<string, unknown>;
  [key: string]: unknown;
};

export type AgentWarning = {
  id: string;
  message: string;
  severity: "low" | "medium" | "high";
};

export type AgentSession = {
  sessionId: string;
  status: AgentSessionStatus;
  currentStep: string;
  messages: AgentMessage[];
  pendingActions: AgentAction[];
  artifacts?: AgentArtifacts;
  warnings?: AgentWarning[];
};
