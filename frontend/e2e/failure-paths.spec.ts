import { test, expect } from '@playwright/test';
import * as path from 'path';
import * as os from 'os';
import * as fs from 'fs';

test.describe('Failure Paths E2E', () => {
  let dummyExePath: string;
  let dummyPdfPath: string;

  test.beforeAll(() => {
    dummyExePath = path.join(os.tmpdir(), 'dummy.exe');
    fs.writeFileSync(dummyExePath, 'MZ...');

    dummyPdfPath = path.join(os.tmpdir(), 'dummy_fail.pdf');
    fs.writeFileSync(dummyPdfPath, 'Dummy PDF content for playwright');
  });

  test.afterAll(() => {
    if (fs.existsSync(dummyExePath)) fs.unlinkSync(dummyExePath);
    if (fs.existsSync(dummyPdfPath)) fs.unlinkSync(dummyPdfPath);
  });

  test('should reject unsupported file types', async ({ page }) => {
    await page.goto('/resumeformatter/formview');

    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.getByRole('button', { name: 'Browse Files' }).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: 'dummy.exe',
      mimeType: 'application/x-msdownload',
      buffer: Buffer.from('MZ...')
    });

    await expect(page.locator('mat-select[formControlName="industry"]')).toBeEnabled();

    await page.getByRole('button', { name: 'Process CV' }).click();

    // API returns 400 Unsupported file type, the UI should handle this
    await expect(page.getByText('An error occurred during processing.')).toBeVisible({ timeout: 10000 });
  });
});
