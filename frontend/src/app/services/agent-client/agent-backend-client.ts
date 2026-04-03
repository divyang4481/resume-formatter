import { InjectionToken } from '@angular/core';
import { AgentSession } from './contracts';

export interface AgentBackendClient {
  createSession(): Promise<AgentSession>;
  uploadDocument(file: File): Promise<AgentSession>;
  getSession(sessionId: string): Promise<AgentSession>;
  answerQuestion(sessionId: string, answer: unknown): Promise<AgentSession>;
  submitCorrection(sessionId: string, correction: unknown): Promise<AgentSession>;
  rerunSession(sessionId: string): Promise<AgentSession>;
  getJobIdFromSession(session: AgentSession | null): string | null;
}

export const AGENT_BACKEND_CLIENT = new InjectionToken<AgentBackendClient>('AgentBackendClient');
