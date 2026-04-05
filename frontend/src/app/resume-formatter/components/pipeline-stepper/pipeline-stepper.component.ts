import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatIconModule } from '@angular/material/icon';
import { MatStepperModule } from '@angular/material/stepper';

@Component({
  selector: 'app-pipeline-stepper',
  standalone: true,
  imports: [CommonModule, MatIconModule, MatStepperModule],
  template: `
    <div class="pipeline-container">
      <div class="pipeline-stages">
        <div *ngFor="let stage of pipelineStages; let i = index" 
             class="stage-item"
             [class.completed]="isCompleted(stage.id)"
             [class.active]="currentStage === stage.id">
          
          <div class="stage-icon-container">
            <mat-icon *ngIf="!isCompleted(stage.id)">{{ stage.icon }}</mat-icon>
            <mat-icon *ngIf="isCompleted(stage.id)" class="done-icon">check_circle</mat-icon>
            
            <div class="progress-line" *ngIf="i < pipelineStages.length - 1"></div>
          </div>
          
          <span class="stage-name">{{ stage.name }}</span>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .pipeline-container {
      padding: 16px;
      background: rgba(255, 255, 255, 0.05);
      border-radius: 12px;
      margin: 8px 0;
      overflow-x: auto;
    }
    .pipeline-stages {
      display: flex;
      justify-content: space-between;
      min-width: 800px;
    }
    .stage-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      flex: 1;
      opacity: 0.4;
      transition: all 0.3s ease;
      position: relative;
    }
    .stage-item.active {
      opacity: 1;
      transform: scale(1.1);
      color: #3f51b5;
    }
    .stage-item.completed {
      opacity: 0.8;
      color: #4caf50;
    }
    .stage-icon-container {
      width: 40px;
      height: 40px;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 8px;
      position: relative;
      z-index: 2;
    }
    .done-icon {
      color: #4caf50;
    }
    .progress-line {
      position: absolute;
      top: 50%;
      left: 100%;
      width: calc(100% - 40px);
      height: 2px;
      background: #e0e0e0;
      transform: translateY(-50%);
      z-index: 1;
    }
    .stage-item.completed .progress-line {
      background: #4caf50;
    }
    .stage-name {
      font-size: 10px;
      font-weight: 500;
      text-align: center;
      white-space: nowrap;
    }
  `]
})
export class PipelineStepperComponent {
  @Input() currentStage: string | null = null;
  @Input() status: string = 'processing';

  pipelineStages = [
    { id: 'ingest', name: 'Ingestion', icon: 'cloud_upload' },
    { id: 'parse', name: 'Parsing', icon: 'document_scanner' },
    { id: 'triage', name: 'Triage', icon: 'rule' },
    { id: 'normalize', name: 'Skills', icon: 'schema' },
    { id: 'privacy', name: 'Privacy', icon: 'security' },
    { id: 'classify', name: 'Matching', icon: 'category' },
    { id: 'transform', name: 'Extraction', icon: 'auto_awesome' },
    { id: 'render', name: 'Rendering', icon: 'picture_as_pdf' },
    { id: 'validate', name: 'Quality', icon: 'fact_check' }
  ];

  isCompleted(stageId: string): boolean {
    if (this.status === 'completed') return true;
    
    const currentIndex = this.pipelineStages.findIndex(s => s.id === this.currentStage);
    const stageIndex = this.pipelineStages.findIndex(s => s.id === stageId);
    
    return stageIndex < currentIndex;
  }
}
