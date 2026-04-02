import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ResumeFormatterComponent } from './resume-formatter.component';

describe('ResumeFormatterComponent', () => {
  let component: ResumeFormatterComponent;
  let fixture: ComponentFixture<ResumeFormatterComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ResumeFormatterComponent],
      providers: [
        { provide: 'ActivatedRoute', useValue: {} }
      ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(ResumeFormatterComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
