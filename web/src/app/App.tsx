import { Route, Routes } from 'react-router';
import { Bootstrap } from '../features/bootstrap/Bootstrap';

export function App() {
  return <Routes><Route path="/" element={<Bootstrap />} /></Routes>;
}
