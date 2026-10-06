import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { beforeEach, afterEach, vi } from 'vitest';

beforeEach(() => { vi.stubGlobal('scrollTo', vi.fn()); });

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
