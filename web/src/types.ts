export type Dictionary = Record<string, unknown>;

export interface IntentPost extends Dictionary {
  intent_id?: string;
  task_id?: string;
  owner_agent_id?: string;
  intent_type?: string;
  public_title?: string;
  public_summary?: string;
  public_constraints?: {
    event?: string;
    location?: string;
    date_start?: string;
    date_end?: string;
    roommate_gender_preference?: string;
  };
  public_requirements?: string[];
  capacity_remaining?: number;
  status?: string;
  version?: number;
  authorship?: { drafted_by_agent_id?: string; approved_by_owner?: boolean };
  demo_data?: boolean;
}

export interface TaskWorkspace extends Dictionary {
  task_id: string;
  title: string;
  task_type: string;
  goal: string;
  status: string;
  conversation_id: string;
  intent_id: string;
  active_room_ids?: string[];
  decision_ids?: string[];
  active_proposal_id?: string;
  match_id?: string;
  updated_at?: string;
}

export interface ConversationMessage extends Dictionary {
  message_id: string;
  conversation_id: string;
  task_id?: string;
  role: "USER" | "PERSONAL_AGENT" | "SYSTEM";
  author_id: string;
  content: string;
  presentation_directive_ids?: string[];
  created_at?: string;
}

export interface PresentationDirective extends Dictionary {
  directive_id: string;
  action: string;
  presentation: "INLINE_CARD" | "SIDE_PANEL" | "NAVIGATE";
  task_id?: string;
  entity_ids: string[];
  explanation: string;
}

export interface Decision extends Dictionary {
  decision_id: string;
  task_id?: string;
  type: string;
  status: string;
  title: string;
  summary: string;
  authoritative_entity_ids: string[];
  expires_at?: string;
}

export interface Assessment extends Dictionary {
  assessment_id: string;
  task_id: string;
  candidate_intent_id: string;
  candidate_agent_id: string;
  priority_band: string;
  current_status: string;
  verified_support: string[];
  peer_reported_support: string[];
  negotiated_support: string[];
  conflicts: string[];
  uncertainties: string[];
  relationship_path: string[];
  active_room_id?: string;
  observable_explanation: string;
}

export interface CoordinationRoom extends Dictionary {
  room_id: string;
  task_id: string;
  source_intent_id: string;
  target_intent_id: string;
  participant_agent_ids: string[];
  room_type: string;
  status: string;
  autonomy_mode: string;
  human_participation_available: boolean;
  latest_meaningful_event: string;
  updated_at?: string;
}

export interface RoomMessage extends Dictionary {
  message_id: string;
  room_id: string;
  task_id: string;
  speaker_id: string;
  speaker_type: string;
  authorship: string;
  visibility: string;
  content: string;
  provenance: Dictionary;
  created_at?: string;
}

export interface ApprovalRequest extends Dictionary {
  runId?: string;
  proposalId?: string;
  proposalVersion?: number;
  status?: string;
  targetIntentId?: string;
  candidateIdentitySummary?: string;
  sharedDates?: { start?: string; end?: string };
  soloDates?: string[];
  costDifferenceUsd?: number;
  delegatedMaximumUsd?: number;
  agreedTerms?: string[];
  remainingUncertainty?: string;
  recommendation?: string;
  informationDisclosed?: string[];
  informationRemainingPrivate?: string[];
  holdExpiresAt?: string;
}

export interface DemoState extends Dictionary {
  product: string;
  executionMode: string;
  exactModelId: string;
  activeIntent: IntentPost | null;
  intentRegistry: IntentPost[];
  peerIntents: IntentPost[];
  intentPairSessions: Dictionary[];
  run: (Dictionary & { runId?: string; status?: string }) | null;
  turns: Dictionary[];
  messages: Dictionary[];
  beliefs: Dictionary[];
  proposals: Dictionary[];
  holds: Dictionary[];
  approvalRequests: ApprovalRequest[];
  approvals: Dictionary[];
  matches: Dictionary[];
  relationships: Dictionary[];
  relationshipEvents: Dictionary[];
  memories: Dictionary[];
  protectedMemoryCount: number;
}

export interface OSBootstrap {
  personalAgent: {
    agentId: string;
    displayName: string;
    ownerDisplayName: string;
    persistentIdentity: boolean;
  };
  tasks: TaskWorkspace[];
  conversations: Dictionary[];
  conversationMessages: ConversationMessage[];
  decisions: Decision[];
  candidateAssessments: Assessment[];
  rooms: CoordinationRoom[];
  roomMessages: RoomMessage[];
  presentationDirectives: PresentationDirective[];
  explorePosts: IntentPost[];
  demoState: DemoState;
  implementationTruth: {
    dynamicWorkersImplemented: boolean;
    peerHumansAreSynthetic: boolean;
    sharedRoomIsSyntheticDemo: boolean;
  };
}

export interface DraftReview {
  publicPost: IntentPost;
  agentOnly: {
    quiet_overnight_compatibility?: { importance?: string; source?: string };
    maximum_additional_cost_usd?: number;
    partial_date_overlap_allowed?: boolean;
  };
  protected: { count: number; summary: string; disclosure: string };
  fieldProvenance: Record<string, string>;
  uncertainties: string[];
}

