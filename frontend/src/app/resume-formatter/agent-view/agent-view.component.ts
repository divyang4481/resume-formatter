import { Component, Inject, OnInit, ViewChild, ElementRef } from '@angular/core';
import { MatStepperModule } from '@angular/material/stepper';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatInputModule } from '@angular/material/input';
import { RouterModule } from '@angular/router';
import { AGENT_BACKEND_CLIENT, AgentBackendClient } from '../../services/agent-client/agent-backend-client';
import { AgentSession } from '../../services/agent-client/contracts';
import { DocumentProcessingService } from '../../services/form-view/document-processing.service';
import { PipelineStepperComponent } from '../components/pipeline-stepper/pipeline-stepper.component';



@Component({
  selector: 'app-agent-view',
  standalone: true,
  imports: [
    MatStepperModule,
    MatIconModule,
    MatButtonModule,
    MatCardModule,
    CommonModule,
    FormsModule,
    MatInputModule,
    RouterModule,
    PipelineStepperComponent
  ],

  templateUrl: './agent-view.component.html',
  styleUrl: './agent-view.component.scss'
})
export class AgentViewComponent implements OnInit {
  session: AgentSession | null = null;
  loading = false;
  chatInput: string = '';

  @ViewChild('fileInput') fileInput!: ElementRef;
  @ViewChild('chatContainer') chatContainer!: ElementRef;

  constructor(
    @Inject(AGENT_BACKEND_CLIENT) public agentClient: AgentBackendClient,
    public docService: DocumentProcessingService
  ) {}

  async ngOnInit(): Promise<void> {
    // Ensure we check for availability
    if (this.docService.industries().length === 0) {
      this.docService.loadIndustries();
    }
    if (this.docService.templates().length === 0) {
      this.docService.loadTemplates();
    }

    this.loading = true;

    try {
      this.session = await this.agentClient.createSession();
      this.checkAndPollJob();
    } catch (e) {
      console.error('Failed to create session', e);
    } finally {
      this.loading = false;
    }
  }

  async startOver(): Promise<void> {
    this.loading = true;
    try {
      this.session = await this.agentClient.createSession();
      this.scrollToBottom();
      this.checkAndPollJob();
    } catch (e) {
      console.error('Failed to start over', e);
    } finally {
      this.loading = false;
    }
  }

  triggerUpload(): void {
    this.fileInput.nativeElement.click();
  }

  async onFileSelected(event: any): Promise<void> {
    const file = event.target.files[0];
    if (!file) return;

    this.loading = true;
    try {
      this.session = await this.agentClient.uploadDocument(file);
      this.checkAndPollJob();
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
      this.scrollToBottom();
      this.checkAndPollJob();
    } catch (e) {
      console.error('Failed to answer question', e);
    } finally {
      this.loading = false;
    }
  }

  async sendChatMessage(): Promise<void> {
    if (!this.chatInput.trim() || !this.session) return;

    const message = this.chatInput;
    this.chatInput = '';
    this.loading = true;

    try {
      this.session = await this.agentClient.answerQuestion(this.session.sessionId, message);
      this.scrollToBottom();
      this.checkAndPollJob();
    } catch (e) {
      console.error('Failed to send message', e);
    } finally {
      this.loading = false;
    }
  }

  private checkAndPollJob(): void {
    if (!this.session) return;

    const jobId = this.agentClient.getJobIdFromSession(this.session);
    if (jobId && (this.session.currentStep === 'processing' || this.session.currentStep === 'review_resume' || this.session.currentStep === 'export')) {
      // If we have a jobId and we are in or past processing, start the polling in the doc service
      // This will fill docService.validationPassed() and docService.validationReport()
      this.docService.pollJobStatus(jobId);
    }
  }

  private scrollToBottom(): void {
    setTimeout(() => {
      if (this.chatContainer) {
        this.chatContainer.nativeElement.scrollTop = this.chatContainer.nativeElement.scrollHeight;
      }
    }, 100);
  }

  getStepIndex(currentStep: string | undefined): number {

    if (!currentStep) return 0;

    // Map internal session steps to the 4 stepper steps
    switch (currentStep) {
      case 'upload_resume':
        return 0; // Upload
      case 'detect_industry':
      case 'choose_template':
        return 1; // Ask for industry and template
      case 'processing':
        return 2; // Processing
      case 'review_resume':
      case 'export':
        return 3; // Result (Export and Summary)
      default:
        return 0;
    }
  }
}
