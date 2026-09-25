import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Dialog } from 'radix-ui';
const client=new QueryClient();
function Probe(){return <Dialog.Root><Dialog.Trigger>Probe</Dialog.Trigger><Dialog.Portal><Dialog.Content><Dialog.Title>Probe</Dialog.Title><Dialog.Description>Synthetic UI only</Dialog.Description></Dialog.Content></Dialog.Portal></Dialog.Root>}
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={client}><BrowserRouter><Routes><Route path="/" element={<Probe/>}/></Routes></BrowserRouter></QueryClientProvider>);
