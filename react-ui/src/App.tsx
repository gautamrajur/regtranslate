import { Routes, Route } from 'react-router-dom'
import { HeroPage } from './HeroPage'
import { Dashboard } from './Dashboard'

function App() {
  return (
    <Routes>
      <Route path="/" element={<HeroPage />} />
      <Route path="/dashboard" element={<Dashboard />} />
    </Routes>
  )
}

export default App
