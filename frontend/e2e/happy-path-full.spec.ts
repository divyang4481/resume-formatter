import { test, expect } from '@playwright/test';
import * as path from 'path';
import * as os from 'os';
import * as fs from 'fs';

test.describe('Happy Path E2E (Full Flow)', () => {
  let dummyPdfPath: string;

  test.beforeAll(() => {
    dummyPdfPath = path.join(os.tmpdir(), 'dummy_resume.txt');
    fs.writeFileSync(dummyPdfPath, 'Dummy TXT content for playwright full');
  });

  test.afterAll(() => {
    if (fs.existsSync(dummyPdfPath)) {
      fs.unlinkSync(dummyPdfPath);
    }
  });

  test('should upload resume, process via worker, and download', async ({ page }) => {
    await page.goto('/resumeformatter/formview');
    await page.waitForSelector('mat-select[formControlName="industry"]');

    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.getByRole('button', { name: 'Browse Files' }).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: 'test_resume_full.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('Test resume content')
    });

    await expect(page.locator('mat-select[formControlName="industry"]')).toBeEnabled();
    await page.getByRole('button', { name: 'Process CV' }).click();

    // Wait for completion from worker. It should poll /jobs/:id and transition eventually
    await expect(page.getByText('Your CV has been successfully formatted.')).toBeVisible({ timeout: 60000 });

    await expect(page.getByRole('link', { name: 'Download Formatted CV' })).toBeVisible();

    // It should fetch and display a summary mock
    await expect(page.getByText('Loading summary...')).toBeHidden({ timeout: 10000 });
  });
});
