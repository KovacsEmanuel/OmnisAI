import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router';
import { App } from './app/App';
import './shared/styles/fonts.css';
import './shared/styles/tokens.css';
import './shared/styles/global.css';

const root = document.getElementById('root');
if (!root) throw new Error('Omnis mount is missing');
const client = new QueryClient({ defaultOptions: {
  queries: { retry: false, refetchOnWindowFocus: true, staleTime: 0 },
  mutations: { retry: false },
} });
createRoot(root).render(<StrictMode><QueryClientProvider client={client}><BrowserRouter><App /></BrowserRouter></QueryClientProvider></StrictMode>);
