import { Injectable } from '@angular/core';
import { AgentBackendClient } from './agent-backend-client';
import { AgentSession, AgentMessage, AgentAction } from './contracts';

@Injectable({
  providedIn: 'root'
})
export class MockAgentBackendClient implements AgentBackendClient {
  private currentSession: AgentSession | null = null;

  async createSession(): Promise<AgentSession> {
    const session: AgentSession = {
      sessionId: 'mock-session-123',
      status: 'idle',
      currentStep: 'upload_resume',
      messages: [
        {
          id: 'm-init',
          role: 'assistant',
          type: 'text',
          content: 'Hello! Please upload your resume to begin.',
          timestamp: new Date().toISOString()
        }
      ],
      pendingActions: [
        {
          id: 'a-upload',
          type: 'upload_document',
          label: 'Upload Document'
        }
      ]
    };

    this.currentSession = session;
    return this.clone(this.currentSession);
  }

  async uploadDocument(file: File): Promise<AgentSession> {
    if (!this.currentSession) await this.createSession();

    // Simulate state transition: processing
    this.currentSession!.status = 'processing';
    this.currentSession!.currentStep = 'detect_industry';
    this.currentSession!.messages.push({
      id: `m-${Date.now()}`,
      role: 'assistant',
      type: 'status',
      content: 'I am parsing your resume and detecting your industry...',
      timestamp: new Date().toISOString()
    });
    this.currentSession!.pendingActions = [];

    // Simulate wait, then waiting for user
    await new Promise(resolve => setTimeout(resolve, 1000));

    this.currentSession!.status = 'waiting_for_user';
    this.currentSession!.currentStep = 'choose_template';
    this.currentSession!.messages.push({
      id: `m-${Date.now()}`,
      role: 'assistant',
      type: 'question',
      content: 'I parsed your resume and detected your industry as <strong>Software Engineering / Tech</strong>. Does that look right?',
      timestamp: new Date().toISOString()
    });

    // Add fake options action
    this.currentSession!.pendingActions = [
      {
        id: 'a-choose-template',
        type: 'select_template',
        label: 'Choose template'
      }
    ];

    return this.clone(this.currentSession!);
  }

  async getSession(sessionId: string): Promise<AgentSession> {
    if (!this.currentSession || this.currentSession.sessionId !== sessionId) {
      return this.createSession();
    }
    return this.clone(this.currentSession);
  }

  async answerQuestion(sessionId: string, answer: unknown): Promise<AgentSession> {
    if (!this.currentSession) return this.createSession();

    const isGenericText = typeof answer === 'string' && answer !== 'Confirmed' && !answer.includes('{');

    this.currentSession.messages.push({
      id: `m-user-${Date.now()}`,
      role: 'user',
      type: 'text',
      content: typeof answer === 'string' ? answer : JSON.stringify(answer),
      timestamp: new Date().toISOString()
    });

    // Simulate response delay
    await new Promise(resolve => setTimeout(resolve, 800));

    if (isGenericText) {
        this.currentSession.messages.push({
            id: `m-agent-ack-${Date.now()}`,
            role: 'assistant',
            type: 'text',
            content: `I received your message: "${answer}". I am a simple resume formatting agent, but I'm here to help you through the process!`,
            timestamp: new Date().toISOString()
        });
    } else {
        this.currentSession.status = 'processing';
        this.currentSession.pendingActions = [];

        this.currentSession.status = 'waiting_for_user';
        this.currentSession.currentStep = 'pii_review';
        this.currentSession.messages.push({
          id: `m-${Date.now()}`,
          role: 'assistant',
          type: 'text',
          content: 'Got it. Now let\'s review the PII policy before we export.',
          timestamp: new Date().toISOString()
        });

        this.currentSession.pendingActions = [
          {
            id: 'a-confirm-pii',
            type: 'confirm_pii_policy',
            label: 'Confirm PII Policy'
          },
          {
            id: 'a-start-over',
            type: 'start_over',
            label: 'Start Over'
          }
        ];
    }

    return this.clone(this.currentSession);
  }

  async submitCorrection(sessionId: string, correction: unknown): Promise<AgentSession> {
    return this.answerQuestion(sessionId, correction);
  }

  async rerunSession(sessionId: string): Promise<AgentSession> {
    return this.createSession();
  }

  private clone<T>(obj: T): T {
    return JSON.parse(JSON.stringify(obj));
  }
}
