import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { beforeEach, afterEach, vi } from 'vitest';

// Legacy domain fixtures isolate the new side-effect adapter; UiDiagnostics.test uses the real binding.
vi.mock('../src/shared/uiDiagnostics', async importOriginal => {
  const actual = await importOriginal<typeof import('../src/shared/uiDiagnostics')>();
  return { ...actual, bindDiagnostics: vi.fn(() => () => {}) };
});

beforeEach(() => { vi.stubGlobal('scrollTo', vi.fn()); });

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
