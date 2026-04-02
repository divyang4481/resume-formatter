import { ComponentFixture, TestBed } from '@angular/core/testing';

import { FormViewComponent } from './form-view.component';

describe('FormViewComponent', () => {
  let component: FormViewComponent;
  let fixture: ComponentFixture<FormViewComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FormViewComponent],
      providers: [
        { provide: 'HttpClient', useValue: {} },
        { provide: 'DocumentProcessingService', useValue: {} },
        { provide: 'RuntimeApiService', useValue: {} }
      ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(FormViewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
