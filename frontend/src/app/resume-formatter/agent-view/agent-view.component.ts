import { Component, Inject, OnInit } from '@angular/core';
import { MatStepperModule } from '@angular/material/stepper';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { CommonModule } from '@angular/common';
import { AGENT_BACKEND_CLIENT, AgentBackendClient } from '../../services/agent-client/agent-backend-client';
import { AgentSession } from '../../services/agent-client/contracts';

@Component({
  selector: 'app-agent-view',
  standalone: true,
  imports: [
    MatStepperModule,
    MatIconModule,
    MatButtonModule,
    MatCardModule,
    CommonModule
  ],
  templateUrl: './agent-view.component.html',
  styleUrl: './agent-view.component.scss'
})
export class AgentViewComponent implements OnInit {
  session: AgentSession | null = null;
  loading = false;

  constructor(
    @Inject(AGENT_BACKEND_CLIENT) private agentClient: AgentBackendClient
  ) {}

  async ngOnInit(): Promise<void> {
    this.loading = true;
    try {
      this.session = await this.agentClient.createSession();
    } catch (e) {
      console.error('Failed to create session', e);
    } finally {
      this.loading = false;
    }
  }

  async triggerUpload(): Promise<void> {
    this.loading = true;
    try {
      // Create a dummy file for the mock
      const file = new File(['dummy content'], 'resume.pdf', { type: 'application/pdf' });
      this.session = await this.agentClient.uploadDocument(file);
    } catch (e) {
      console.error('Failed to upload document', e);
    } finally {
      this.loading = false;
    }
  }

  async answerQuestion(answer: unknown): Promise<void> {
    if (!this.session) return;
    this.loading = true;
    try {
      this.session = await this.agentClient.answerQuestion(this.session.sessionId, answer);
    } catch (e) {
      console.error('Failed to answer question', e);
    } finally {
      this.loading = false;
    }
  }

  getStepIndex(currentStep: string | undefined): number {
    const steps = ['upload_resume', 'detect_industry', 'choose_template', 'pii_review', 'export'];
    const idx = steps.indexOf(currentStep || 'upload_resume');
    return idx === -1 ? 0 : idx;
  }
}
