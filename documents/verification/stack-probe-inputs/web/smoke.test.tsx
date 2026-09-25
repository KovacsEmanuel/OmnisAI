import React from 'react';
import { test, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router';
import { Dialog } from 'radix-ui';
test('router and accessible dialog render and respond', async()=>{
render(<MemoryRouter><Routes><Route path="/" element={<Dialog.Root><Dialog.Trigger>Open probe</Dialog.Trigger><Dialog.Portal><Dialog.Content><Dialog.Title>Probe title</Dialog.Title><Dialog.Description>Only dependency verification</Dialog.Description></Dialog.Content></Dialog.Portal></Dialog.Root>}/></Routes></MemoryRouter>);
await userEvent.click(screen.getByRole('button',{name:'Open probe'}));
expect(screen.getByRole('dialog')).toBeInTheDocument();
expect(screen.getByText('Probe title')).toBeVisible();
});
