import { Injectable } from '@angular/core';
import { AgentBackendClient } from './agent-backend-client';
import { AgentSession, AgentMessage, AgentAction } from './contracts';
import { ProcessingApiService, Template } from '../api/processing-api.service';
import { firstValueFrom } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class RealAgentBackendClient implements AgentBackendClient {
  private currentSession: AgentSession | null = null;

  constructor(private runtimeApi: ProcessingApiService) {}

  getJobIdFromSession(session: AgentSession | null): string | null {
    if (!session || !session.artifacts) return null;
    return session.artifacts['jobId'] as string || null;
  }

  async createSession(): Promise<AgentSession> {
    const session: AgentSession = {
      sessionId: 'session-' + Date.now(),
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
    if (!this.currentSession) {
      this.currentSession = await this.createSession();
    }

    this.currentSession.status = 'uploading';
    this.currentSession.messages.push({
      id: `m-user-upload-${Date.now()}`,
      role: 'user',
      type: 'text',
      content: `Uploaded file: ${file.name}`,
      timestamp: new Date().toISOString()
    });
    this.currentSession.pendingActions = [];

    try {
      const res = await firstValueFrom(this.runtimeApi.submitDocument(file));
      this.currentSession.sessionId = res.job_id; // Using job_id as sessionId
      if (!this.currentSession.artifacts) this.currentSession.artifacts = {};
      this.currentSession.artifacts['jobId'] = res.job_id;

      if (res.requires_confirmation) {
        this.currentSession.status = 'waiting_for_user';
        this.currentSession.currentStep = 'choose_template';

        let msg = 'I parsed your resume.';
        if (res.suggested_industry_id) {
          msg += ` I detected your industry as <strong>${res.suggested_industry_id}</strong>.`;
        }
        msg += ' Please choose a template.';

        this.currentSession.messages.push({
          id: `m-status-${Date.now()}`,
          role: 'assistant',
          type: 'question',
          content: msg,
          timestamp: new Date().toISOString()
        });

        // Fetch templates for the suggested industry
        const templatesRes = await firstValueFrom(this.runtimeApi.getTemplates(res.suggested_industry_id));

        this.currentSession.pendingActions = [
          {
            id: 'a-choose-template',
            type: 'select_template',
            label: 'Choose template',
            payload: {
                industry_id: res.suggested_industry_id,
                templates: templatesRes.templates
            }
          }
        ];
      } else {
        this.currentSession.status = 'processing';
        this.currentSession.currentStep = 'review_resume';
        this.currentSession.messages.push({
          id: `m-status-${Date.now()}`,
          role: 'assistant',
          type: 'status',
          content: 'Processing document...',
          timestamp: new Date().toISOString()
        });
        await this.waitForJobCompletion(res.job_id);
      }
    } catch (e) {
      this.currentSession.status = 'failed';
      this.currentSession.messages.push({
        id: `m-error-${Date.now()}`,
        role: 'assistant',
        type: 'text',
        content: 'Failed to upload document. Please try again.',
        timestamp: new Date().toISOString()
      });
    }

    return this.clone(this.currentSession);
  }

  async getSession(sessionId: string): Promise<AgentSession> {
    if (!this.currentSession || this.currentSession.sessionId !== sessionId) {
      return this.createSession();
    }
    return this.clone(this.currentSession);
  }

  async answerQuestion(sessionId: string, answer: any): Promise<AgentSession> {
    if (!this.currentSession) return this.createSession();

    if (this.currentSession.currentStep === 'choose_template' && answer && answer.template_id) {
        this.currentSession.messages.push({
            id: `m-user-${Date.now()}`,
            role: 'user',
            type: 'text',
            content: `Selected template: ${answer.template_id}`,
            timestamp: new Date().toISOString()
        });

        this.currentSession.status = 'processing';
        this.currentSession.pendingActions = [];
        this.currentSession.currentStep = 'review_resume';

        try {
             await firstValueFrom(this.runtimeApi.confirmDocument(
                sessionId,
                answer.industry_id || 'it',
                answer.template_id
            ));
             this.currentSession.messages.push({
                id: `m-status-${Date.now()}`,
                role: 'assistant',
                type: 'status',
                content: 'Template confirmed. Processing document...',
                timestamp: new Date().toISOString()
             });
             await this.waitForJobCompletion(sessionId);
        } catch(e) {
            this.currentSession.status = 'failed';
            this.currentSession.messages.push({
                id: `m-error-${Date.now()}`,
                role: 'assistant',
                type: 'text',
                content: 'Failed to confirm document. Please try again.',
                timestamp: new Date().toISOString()
            });
        }
    } else if (this.currentSession.currentStep === 'review_resume' && answer === 'Confirmed') {
        this.currentSession.messages.push({
            id: `m-user-${Date.now()}`,
            role: 'user',
            type: 'text',
            content: 'Confirmed Review',
            timestamp: new Date().toISOString()
        });

        this.currentSession.status = 'completed';
        this.currentSession.pendingActions = [];
        this.currentSession.currentStep = 'export';

        try {
            const summaryRes = await firstValueFrom(this.runtimeApi.getJobSummary(sessionId));
            this.currentSession.messages.push({
                id: `m-summary-${Date.now()}`,
                role: 'assistant',
                type: 'result',
                content: `Processing complete! Summary: ${summaryRes.summary}`,
                timestamp: new Date().toISOString()
            });

        if (!this.currentSession.artifacts) this.currentSession.artifacts = {};
        this.currentSession.artifacts['jobId'] = sessionId;

            const outputRes = await firstValueFrom(this.runtimeApi.getJobOutput(sessionId));
            this.currentSession.pendingActions = [
               {
                 id: 'a-download',
                 type: 'download_output',
                 label: 'Download Output',
                 payload: { url: outputRes.url }
               },
               {
                 id: 'a-start-over',
                 type: 'start_over',
                 label: 'Start Over'
               }
            ];
        } catch(e) {
            this.currentSession.status = 'failed';
            this.currentSession.messages.push({
                id: `m-error-${Date.now()}`,
                role: 'assistant',
                type: 'text',
                content: 'Failed to retrieve results. Please try again.',
                timestamp: new Date().toISOString()
            });
        }
    } else {
        // Fallback for other answers (generic chat messages)
        const userMessageContent = typeof answer === 'string' ? answer : JSON.stringify(answer);

        this.currentSession.messages.push({
            id: `m-user-${Date.now()}`,
            role: 'user',
            type: 'text',
            content: userMessageContent,
            timestamp: new Date().toISOString()
        });

        // Add a generic acknowledgement from the agent
        this.currentSession.messages.push({
            id: `m-agent-ack-${Date.now()}`,
            role: 'assistant',
            type: 'text',
            content: `I received your message: "${userMessageContent}". I am a simple resume formatting agent, but I'm here to help you through the process!`,
            timestamp: new Date().toISOString()
        });
    }

    return this.clone(this.currentSession);
  }

  async submitCorrection(sessionId: string, correction: unknown): Promise<AgentSession> {
    return this.answerQuestion(sessionId, correction);
  }

  async rerunSession(sessionId: string): Promise<AgentSession> {
    return this.createSession();
  }

  private async waitForJobCompletion(jobId: string): Promise<void> {
    let lastStage: string | null = null;
    while (true) {
        try {
            const statusRes = await firstValueFrom(this.runtimeApi.getJobStatus(jobId));

            // Output polling messages
            if (this.currentSession && statusRes.stage && statusRes.stage !== lastStage) {
                lastStage = statusRes.stage;
                const stageMessage = this.getStageMessage(statusRes.stage);
                if (stageMessage) {
                    this.currentSession.messages.push({
                        id: `m-stage-${Date.now()}`,
                        role: 'assistant',
                        type: 'status',
                        content: stageMessage,
                        timestamp: new Date().toISOString()
                    });
                }

                // Keep the UI current step roughly mapped during polling so stepper might reflect progress
                if (['ingest', 'parse'].includes(statusRes.stage)) {
                    this.currentSession.currentStep = 'detect_industry';
                } else if (['classify'].includes(statusRes.stage)) {
                    this.currentSession.currentStep = 'choose_template';
                } else {
                    this.currentSession.currentStep = 'processing';
                }
            }

            if (statusRes.status === 'completed') {
                if (this.currentSession) {
                    this.currentSession.status = 'waiting_for_user';
                    this.currentSession.currentStep = 'review_resume';
                    this.currentSession.messages.push({
                        id: `m-status-${Date.now()}`,
                        role: 'assistant',
                        type: 'text',
                        content: 'Document processing completed. Please review the generated resume before we export.',
                        timestamp: new Date().toISOString()
                    });
                    this.currentSession.pendingActions = [
                        {
                            id: 'a-confirm-review',
                            type: 'confirm_review',
                            label: 'Confirm Review'
                        }
                    ];
                }
                break;
            } else if (statusRes.status === 'failed') {
                if (this.currentSession) {
                    this.currentSession.status = 'failed';
                    this.currentSession.messages.push({
                        id: `m-error-${Date.now()}`,
                        role: 'assistant',
                        type: 'text',
                        content: 'Job failed during processing.',
                        timestamp: new Date().toISOString()
                    });
                }
                break;
            }
            // Wait before polling again
            await new Promise(resolve => setTimeout(resolve, 2000));
        } catch(e) {
            console.error('Error polling job status', e);
            if (this.currentSession) {
                this.currentSession.status = 'failed';
                this.currentSession.messages.push({
                    id: `m-error-${Date.now()}`,
                    role: 'assistant',
                    type: 'text',
                    content: 'Error checking job status.',
                    timestamp: new Date().toISOString()
                });
            }
            break;
        }
    }
  }

  private getStageMessage(stage: string): string | null {
    const messages: Record<string, string> = {
        'ingest': 'Ingesting document...',
        'parse': 'Parsing contents...',
        'normalize': 'Normalizing data...',
        'privacy': 'Applying privacy filters...',
        'classify': 'Classifying resume...',
        'transform': 'Transforming content for the template...',
        'render': 'Rendering final document...',
        'validate': 'Validating output...'
    };
    return messages[stage] || `Processing stage: ${stage}...`;
  }

  private clone<T>(obj: T): T {
    return JSON.parse(JSON.stringify(obj));
  }
}
