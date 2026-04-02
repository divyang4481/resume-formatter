import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AgentViewComponent } from './agent-view.component';

import { AGENT_BACKEND_CLIENT } from '../../services/agent-client/agent-backend-client';
import { MockAgentBackendClient } from '../../services/agent-client/mock-agent-backend-client';

describe('AgentViewComponent', () => {
  let component: AgentViewComponent;
  let fixture: ComponentFixture<AgentViewComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AgentViewComponent],
      providers: [
        { provide: AGENT_BACKEND_CLIENT, useClass: MockAgentBackendClient }
      ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(AgentViewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
